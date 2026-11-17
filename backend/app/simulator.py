"""Simulador de la flota de ovitrampas IoT que corre dentro del backend.

Emula el flujo continuo de telemetría mientras no existan nodos físicos:
- Cada `SIMULATOR_INTERVAL` segundos, algunos nodos en línea envían su
  lectura de microclima (en el diseño real: cada 15 min por nodo).
- Cada nodo envía su conteo diario de huevecillos a su hora programada.
- Ocasionalmente se genera una lectura anómala (va a cuarentena) y un
  reporte ciudadano de criadero.
- Cada hora: actualiza clima real, agrega semanas de casos y depura datos viejos.

Todas las lecturas pasan por la misma función de ingesta y validación que
usa el endpoint POST /api/telemetry.
"""
import logging
import math
import random
import threading

from sqlalchemy import select

from . import seed, weather
from .db import SessionLocal
from .models import CitizenReport, Node, WeatherDaily
from .simdata import PROFILES
from .telemetry import ReadingIn, ingest_reading
from .timeutil import local_now, local_today, utcnow

log = logging.getLogger("sentinela.simulator")


class FleetSimulator:
    def __init__(self, interval: float):
        self.interval = max(1.0, interval)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.ticks = 0
        self.rng = random.Random()
        self._online: list[tuple[str, str, str]] = []
        self._wx: dict[str, tuple[float, float]] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="fleet-simulator", daemon=True)
        self._thread.start()
        log.info("Simulador de flota IoT iniciado (cada %.0f s)", self.interval)

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.tick()
            except Exception:  # el simulador nunca debe tumbar el servidor
                log.exception("Error en el ciclo del simulador")

    def _refresh_cache(self, db) -> None:
        self._online = [(n.id, n.area_id, n.municipio_id) for n in db.scalars(
            select(Node).where(Node.sim_offline.is_(False))).all()]
        today = local_today()
        self._wx = {a: (tmin, tmax) for a, tmin, tmax in db.execute(
            select(WeatherDaily.area_id, WeatherDaily.tmin, WeatherDaily.tmax).where(WeatherDaily.day == today)).all()}

    def _climate(self, node_id: str, area_id: str, mun_id: str) -> ReadingIn:
        tmin, tmax = self._wx.get(area_id) or self._wx.get(mun_id) or (22.5, 31.0)
        hour = local_now().hour + local_now().minute / 60
        frac = max(0.0, math.sin(math.pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0.0
        temp = tmin + (tmax - tmin) * frac + self.rng.uniform(-0.6, 0.6)
        hum = 95 - 35 * frac + self.rng.uniform(-4, 4)
        return ReadingIn(node_id=node_id, kind="clima", temp_c=round(temp, 1), humidity=round(min(100, hum), 1),
                         battery_v=round(self.rng.uniform(3.7, 4.12), 2), rssi=int(self.rng.uniform(-118, -70)))

    def tick(self) -> None:
        self.ticks += 1
        with SessionLocal() as db:
            if self.ticks == 1 or self.ticks % 60 == 0:
                self._refresh_cache(db)
            if not self._online:
                return
            # 1) Microclima de 2 a 4 nodos.
            for node_id, area_id, mun_id in self.rng.sample(self._online, k=min(len(self._online), self.rng.randint(2, 4))):
                ingest_reading(db, self._climate(node_id, area_id, mun_id), source="sim")
            # 2) Lectura anómala ocasional (~6 por hora; prueba de la regla de cuarentena).
            if self.rng.random() < self.interval / 600:
                node_id, _a, _m = self.rng.choice(self._online)
                bad = self.rng.choice([
                    ReadingIn(node_id=node_id, kind="clima", temp_c=round(self.rng.uniform(61, 85), 1), humidity=40.0),
                    ReadingIn(node_id=node_id, kind="huevos", eggs_count=9999, eggs_delta=9999),
                    ReadingIn(node_id=node_id, kind="clima", temp_c=27.0, humidity=80.0, battery_v=7.9),
                ])
                ingest_reading(db, bad, source="sim")
            # 3) Reportes ciudadanos al ritmo esperado del día (criaderos por día de cada área).
            today = local_today()
            daily_rate = sum(p.criaderos_per_day(today) for p in PROFILES.values())
            if self.rng.random() < daily_rate * self.interval / 86400:
                areas = list(PROFILES)
                weights = [PROFILES[a].criaderos_per_day(today) + 0.01 for a in areas]
                area_id = self.rng.choices(areas, weights=weights)[0]
                photo = self.rng.random() < 0.95
                db.add(CitizenReport(area_id=area_id, description="Reporte ciudadano (app / WhatsApp)", has_photo=photo,
                                     status="validado" if photo and self.rng.random() < 0.93 else "pendiente",
                                     created_at=utcnow(), source="sim"))
            db.commit()
            # 4) Conteos diarios de huevecillos que ya tocan (hora programada de cada nodo).
            if self.ticks % 12 == 0:
                seed.backfill_readings(db)
            # 5) Tareas horarias.
            if self.ticks % max(1, int(3600 / self.interval)) == 0:
                weather.refresh_weather(db)
                seed.backfill_cases(db)
                seed.backfill_reports(db)
                seed.retention_cleanup(db)
                self._refresh_cache(db)
