"""Punto de entrada: uvicorn app.main:app

Al arrancar: crea tablas, siembra la base si está vacía, trae clima real de
Open-Meteo, rellena las series hasta hoy (backfill), opcionalmente carga casos
reales de la DGE y enciende el simulador de la flota IoT. La inicialización
corre en un hilo para que el servidor abra el puerto de inmediato (Render
exige que el puerto responda pronto); mientras tanto los endpoints de datos
responden 503 y el tablero reintenta.
"""
import logging
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (registra las tablas)
from . import seed, weather
from .api import router
from .config import settings
from .db import Base, SessionLocal, db_kind, engine
from .simulator import FleetSimulator
from .state import app_state

for _stream in (sys.stdout, sys.stderr):  # acentos correctos en la consola de Windows
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sentinela")


def initialize() -> None:
    try:
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            if seed.seed_if_empty(db):
                log.info("Catálogo y nodos creados")
            weather.refresh_weather(db)
            seed.backfill_cases(db)
            seed.backfill_reports(db)
            n = seed.backfill_readings(db)
            seed.retention_cleanup(db)
            if settings.dge_etl_enabled:
                try:
                    from . import etl_dge
                    log.info("Cargando casos reales de la DGE…")
                    log.info("DGE: %s", etl_dge.load(db, etl_dge.download()))
                except Exception as exc:
                    db.rollback()
                    log.warning("No se pudieron cargar los datos de la DGE: %s", exc)
        log.info("Base lista (%s); %s lecturas nuevas en el backfill", db_kind(), n)
        app_state.ready = True
        if settings.simulator_enabled:
            app_state.simulator = FleetSimulator(settings.simulator_interval)
            app_state.simulator.start()
    except Exception as exc:  # se reporta en /api/health
        app_state.init_error = str(exc)
        log.exception("Fallo en la inicialización")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=initialize, name="init", daemon=True).start()
    yield
    if app_state.simulator:
        app_state.simulator.stop()


app = FastAPI(
    title="Sentinela Aedes API",
    version="1.0.0",
    description=(
        "Backend del prototipo alfa de Sentinela Aedes: ingesta de telemetría de ovitrampas IoT, "
        "clima real (Open-Meteo), modelo de riesgo de brote de dengue por colonia/municipio, pronóstico "
        "estatal e integración simulada con el ERP de la Secretaría de Salud."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Device-Key"],
)
app.include_router(router)


@app.api_route("/", methods=["GET", "HEAD"], tags=["sistema"])
def root():
    return {
        "servicio": "Sentinela Aedes API",
        "estado": "lista" if app_state.ready else "inicializando",
        "documentacion": "/docs",
        "endpoints": ["/api/health", "/api/dashboard", "/api/ops", "/api/telemetry", "/api/brigadas",
                      "/api/reportes", "/api/erp/transacciones"],
    }
