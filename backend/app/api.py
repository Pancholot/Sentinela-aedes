"""Endpoints REST de Sentinela Aedes."""
import ipaddress
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import erp
from .analytics import LEVELS, dashboard_cache, level_of
from .config import settings
from .db import get_db
from .models import (
    Area,
    BrigadeAssignment,
    CitizenReport,
    ErpTransaction,
    Node,
    QuarantinedReading,
    Reading,
    SecurityEvent,
)
from .state import app_state
from .telemetry import BatchIn, ReadingIn, ingest_reading, reading_payload, register_auth_failure
from .timeutil import iso_utc, utcnow

router = APIRouter(prefix="/api")


def require_ready():
    if not app_state.ready:
        raise HTTPException(status_code=503, detail="El servidor está inicializando la base de datos; reintenta en unos segundos.")


def client_ip(request: Request) -> str:
    """IP del cliente para la regla SIEM.

    X-Forwarded-For llega como "<lo que mandó el cliente>, <IP real>, <proxies internos>".
    Los primeros valores los puede falsificar un atacante para evadir el umbral por IP,
    y los últimos son IPs privadas de la red de Render. Por eso se toma la IP pública
    más a la derecha: la que agregó el borde de Render con quien realmente se conectó."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        for part in reversed([p.strip() for p in fwd.split(",") if p.strip()]):
            try:
                if ipaddress.ip_address(part).is_global:
                    return part
            except ValueError:
                continue
    return request.client.host if request.client else "desconocida"


# ------------------------------------------------------------------ estado

@router.get("/health", tags=["sistema"])
def health():
    return {"status": "ok" if app_state.ready else "starting", "ready": app_state.ready,
            "init_error": app_state.init_error, "time": iso_utc(utcnow()),
            "simulator": app_state.simulator.running if app_state.simulator else False}


@router.get("/dashboard", tags=["tablero"], dependencies=[Depends(require_ready)])
def dashboard(db: Session = Depends(get_db)):
    """Todo lo que necesita el tablero en una sola llamada (se consulta cada 10 s)."""
    return dashboard_cache.get(db)


@router.get("/kpis", tags=["tablero"], dependencies=[Depends(require_ready)])
def kpis(db: Session = Depends(get_db)):
    d = dashboard_cache.get(db)
    return {"meta": d["meta"], "kpis": d["kpis"]}


@router.get("/colonias", tags=["tablero"], dependencies=[Depends(require_ready)])
def colonias(db: Session = Depends(get_db)):
    return dashboard_cache.get(db)["colonias"]


@router.get("/colonias/{slug}", tags=["tablero"], dependencies=[Depends(require_ready)])
def colonia(slug: str, db: Session = Depends(get_db)):
    for c in dashboard_cache.get(db)["colonias"]:
        if c["id"] == slug:
            return c
    raise HTTPException(404, "Colonia no encontrada")


@router.get("/municipios", tags=["tablero"], dependencies=[Depends(require_ready)])
def municipios(db: Session = Depends(get_db)):
    return dashboard_cache.get(db)["municipios"]


@router.get("/forecast", tags=["tablero"], dependencies=[Depends(require_ready)])
def forecast(db: Session = Depends(get_db)):
    return dashboard_cache.get(db)["forecast"]


# --------------------------------------------------------------- telemetría

def _check_device_key(request: Request, db: Session, key: str | None) -> None:
    if not key or not secrets.compare_digest(key, settings.device_api_key):
        register_auth_failure(db, client_ip(request), f"Llave de dispositivo inválida en {request.url.path}")
        raise HTTPException(status_code=401, detail="Llave de dispositivo inválida")


@router.post("/telemetry", tags=["telemetría"], dependencies=[Depends(require_ready)])
def post_telemetry(payload: ReadingIn | BatchIn, request: Request, db: Session = Depends(get_db),
                   x_device_key: str | None = Header(None)):
    """Ingesta de telemetría desde nodos o gateways (requiere encabezado X-Device-Key).

    Acepta una lectura o un lote `{"gateway_id": ..., "readings": [...]}`."""
    _check_device_key(request, db, x_device_key)
    items = payload.readings if isinstance(payload, BatchIn) else [payload]
    results = []
    for r in items:
        ok, reason = ingest_reading(db, r, source="device", ip=client_ip(request))
        results.append({"node_id": r.node_id, "accepted": ok, "detail": reason})
    db.commit()
    accepted = sum(1 for x in results if x["accepted"])
    return {"received": len(results), "accepted": accepted, "quarantined": len(results) - accepted, "results": results}


@router.get("/telemetry/recent", tags=["telemetría"], dependencies=[Depends(require_ready)])
def recent_telemetry(limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    names = {a.id: a.name for a in db.scalars(select(Area)).all()}
    area_of = {n.id: n.area_id for n in db.scalars(select(Node)).all()}
    rows = db.scalars(select(Reading).order_by(Reading.id.desc()).limit(limit)).all()
    return [reading_payload(r, names.get(area_of.get(r.node_id, ""), "")) for r in rows]


@router.get("/nodes", tags=["telemetría"], dependencies=[Depends(require_ready)])
def list_nodes(status: str | None = Query(None, pattern="^(online|offline)$"), db: Session = Depends(get_db)):
    names = {a.id: a.name for a in db.scalars(select(Area)).all()}
    cut = utcnow() - timedelta(hours=48)
    out = []
    for n in db.scalars(select(Node).order_by(Node.id)).all():
        online = bool(n.last_seen and n.last_seen >= cut and not n.sim_offline)
        if status == "online" and not online or status == "offline" and online:
            continue
        out.append({"id": n.id, "area": names.get(n.area_id), "municipio": names.get(n.municipio_id),
                    "connectivity": n.connectivity, "status": n.status, "online": online,
                    "last_seen": iso_utc(n.last_seen), "battery_v": n.battery_v, "lat": round(n.lat, 5),
                    "lon": round(n.lon, 5)})
    return out


# ---------------------------------------------------- acciones + ERP simulado

class BrigadaIn(BaseModel):
    area_id: str = Field(..., examples=["col:mulsay", "mun:sotuta"])
    horizon: int = Field(1, ge=0, le=2, description="Índice del horizonte: 0 = 1 semana, 1 = 2 semanas, 2 = 4 semanas")


@router.post("/brigadas", tags=["acciones"], dependencies=[Depends(require_ready)])
def asignar_brigada(body: BrigadaIn, db: Session = Depends(get_db)):
    """Asigna una brigada de control vectorial y envía la orden de servicio al ERP (simulado)."""
    area = db.get(Area, body.area_id)
    if area is None or area.kind not in ("colonia", "municipio"):
        raise HTTPException(404, "Área no encontrada")
    data = dashboard_cache.get(db)
    items = data["colonias"] if area.kind == "colonia" else data["municipios"]
    item = next(i for i in items if i["key"] == area.id)
    p = item["p"][body.horizon]
    lvl = level_of(p)
    existing = db.scalar(select(BrigadeAssignment).where(
        BrigadeAssignment.area_id == area.id, BrigadeAssignment.created_at >= utcnow() - timedelta(days=7)))
    if existing:
        tx = db.scalar(select(ErpTransaction).where(ErpTransaction.folio == existing.erp_folio))
        return {"created": False, "message": "Ya hay una brigada asignada esta semana",
                "assignment": {"area_id": area.id, "folio": existing.erp_folio}, "erp": erp.tx_payload(tx) if tx else None}
    horizon_weeks = [1, 2, 4][body.horizon]
    lineas = erp.requisicion_brigada(area.viviendas if area.kind == "colonia" else None, lvl)
    datos = {
        "clase_orden": "CONTROL_VECTORIAL",
        "prioridad": ["BAJA", "MEDIA", "ALTA", "URGENTE"][lvl],
        "ubicacion": {"tipo": area.kind, "clave": area.id, "nombre": area.name, "lat": area.lat, "lon": area.lon,
                      "municipio": "Mérida" if area.kind == "colonia" else area.name},
        "motivo": f"Probabilidad de brote de dengue de {p}% a {horizon_weeks} semana(s) · nivel {LEVELS[lvl]}",
        "variables_principales": [d["text"] for d in item["drivers"]],
        "fecha_limite_dias": 2 if lvl == 3 else 7,
        "partidas": lineas,
        "importe_total_mxn": round(sum(x["importe"] for x in lineas), 2),
        "notificar": ["Jurisdicción Sanitaria 1"] + (["Hospitales de la zona", "Ayuntamiento"] if lvl == 3 else []),
    }
    tx = erp.enviar_a_erp(db, "ORDEN_SERVICIO", datos,
                          f"Brigada de control vectorial · {area.name} · riesgo {LEVELS[lvl]} {p}%", area.id)
    db.add(BrigadeAssignment(area_id=area.id, created_at=utcnow(), risk_p=p, risk_level=LEVELS[lvl],
                             horizon_weeks=horizon_weeks, status="asignada", erp_folio=tx.folio))
    db.commit()
    dashboard_cache.invalidate()
    return {"created": True, "message": f"Orden de servicio {tx.folio} enviada al ERP",
            "assignment": {"area_id": area.id, "folio": tx.folio}, "erp": erp.tx_payload(tx, include_document=True)}


@router.get("/brigadas", tags=["acciones"], dependencies=[Depends(require_ready)])
def listar_brigadas(db: Session = Depends(get_db)):
    names = {a.id: a.name for a in db.scalars(select(Area)).all()}
    rows = db.scalars(select(BrigadeAssignment).order_by(BrigadeAssignment.id.desc()).limit(100)).all()
    return [{"area_id": b.area_id, "area": names.get(b.area_id), "created_at": iso_utc(b.created_at), "risk_p": b.risk_p,
             "risk_level": b.risk_level, "horizon_weeks": b.horizon_weeks, "status": b.status, "erp_folio": b.erp_folio}
            for b in rows]


class ReporteIn(BaseModel):
    colonia: str = Field(..., examples=["mulsay"])
    descripcion: str = Field("", max_length=500)
    con_foto: bool = False


@router.post("/reportes", tags=["acciones"], dependencies=[Depends(require_ready)])
def crear_reporte(body: ReporteIn, db: Session = Depends(get_db)):
    """Reporte ciudadano de criadero: se guarda y genera un aviso de servicio en el ERP (simulado)."""
    area = db.get(Area, f"col:{body.colonia}")
    if area is None:
        raise HTTPException(404, "Colonia no encontrada")
    status = "validado" if body.con_foto else "pendiente"
    rep = CitizenReport(area_id=area.id, description=body.descripcion.strip() or "Sin descripción",
                        has_photo=body.con_foto, status=status, created_at=utcnow(), source="app")
    db.add(rep)
    db.flush()
    rep.folio = f"SA-{utcnow().year}-{rep.id:05d}"
    tx = erp.enviar_a_erp(db, "AVISO_CIUDADANO", {
        "clase_aviso": "CRIADERO_REPORTADO", "folio_ciudadano": rep.folio,
        "ubicacion": {"colonia": area.name, "municipio": "Mérida", "precision_m": 100},
        "descripcion": rep.description, "evidencia_foto": body.con_foto,
        "validacion_automatica": status, "prioridad": "MEDIA",
    }, f"Criadero reportado · {area.name} · folio {rep.folio}", area.id)
    rep.erp_folio = tx.folio
    db.commit()
    dashboard_cache.invalidate()
    return {"folio": rep.folio, "status": status, "erp": erp.tx_payload(tx)}


@router.post("/erp/mantenimiento", tags=["ERP simulado"], dependencies=[Depends(require_ready)])
def ordenes_mantenimiento(db: Session = Depends(get_db)):
    """Genera una orden de mantenimiento en el ERP por los nodos sin datos en 48 h."""
    cut = utcnow() - timedelta(hours=48)
    names = {a.id: a.name for a in db.scalars(select(Area)).all()}
    offline = [n for n in db.scalars(select(Node).order_by(Node.id)).all()
               if n.sim_offline or not n.last_seen or n.last_seen < cut]
    pending = [n for n in offline if n.status != "mantenimiento_programado"]
    if not pending:
        return {"created": False, "message": "No hay nodos pendientes de mantenimiento", "nodes": len(offline)}
    lineas = [erp.partida("REF-NODO", len(pending)), erp.partida("HH-TECNICO", len(pending) * 1.5)]
    tx = erp.enviar_a_erp(db, "ORDEN_MANTENIMIENTO", {
        "clase_orden": "MANTENIMIENTO_CORRECTIVO_IOT",
        "equipos": [{"nodo": n.id, "ubicacion": names.get(n.area_id), "ultima_lectura": iso_utc(n.last_seen),
                     "bateria_v": n.battery_v} for n in pending],
        "partidas": lineas, "importe_total_mxn": round(sum(x["importe"] for x in lineas), 2),
        "responsable": "Equipo técnico Sentinela Aedes",
    }, f"Mantenimiento de {len(pending)} nodos IoT sin datos > 48 h")
    for n in pending:
        n.status = "mantenimiento_programado"
    db.commit()
    return {"created": True, "message": f"Orden {tx.folio} enviada al ERP", "nodes": len(pending),
            "erp": erp.tx_payload(tx)}


@router.post("/erp/sync-kpis", tags=["ERP simulado"], dependencies=[Depends(require_ready)])
def sincronizar_kpis(db: Session = Depends(get_db)):
    """Envía al ERP los indicadores de la semana (casos pronosticados, colonias en riesgo, IPO, nodos)."""
    d = dashboard_cache.get(db)
    k, f = d["kpis"], d["forecast"]
    riesgo = {LEVELS[i]: sum(1 for c in d["colonias"] if level_of(c["p"][1]) == i) for i in range(4)}
    tx = erp.enviar_a_erp(db, "REPORTE_KPI", {
        "periodo": f"{d['meta']['epi_year']}-S{d['meta']['epi_week']:02d}",
        "casos_pronosticados": dict(zip(["1_semana", "2_semanas", "3_semanas", "4_semanas"], f["mean"])),
        "umbral_epidemico": f["threshold"], "colonias_por_nivel_2_semanas": riesgo,
        "ipo_estatal": k["ipo"], "nodos_en_linea": f"{k['nodes_online']}/{k['nodes_total']}",
        "reportes_validados_7_dias": k["reports_validated"],
    }, f"KPIs semana {d['meta']['epi_week']} · IPO {k['ipo']}% · {k['nodes_online']}/{k['nodes_total']} nodos")
    db.commit()
    return {"created": True, "message": f"Reporte {tx.folio} enviado al ERP", "erp": erp.tx_payload(tx)}


@router.get("/erp/transacciones", tags=["ERP simulado"], dependencies=[Depends(require_ready)])
def transacciones(limit: int = Query(20, ge=1, le=200), detalle: bool = False, db: Session = Depends(get_db)):
    rows = db.scalars(select(ErpTransaction).order_by(ErpTransaction.id.desc()).limit(limit)).all()
    return [erp.tx_payload(t, include_document=detalle) for t in rows]


@router.get("/erp/transacciones/{folio}", tags=["ERP simulado"], dependencies=[Depends(require_ready)])
def transaccion(folio: str, db: Session = Depends(get_db)):
    tx = db.scalar(select(ErpTransaction).where(ErpTransaction.folio == folio))
    if tx is None:
        raise HTTPException(404, "Folio no encontrado")
    return erp.tx_payload(tx, include_document=True)


# ------------------------------------------------------------- operación

@router.post("/admin/reset-demo", tags=["sistema"], dependencies=[Depends(require_ready)])
def reset_demo(request: Request, db: Session = Depends(get_db), x_device_key: str | None = Header(None)):
    """Limpia lo generado durante pruebas (brigadas, documentos ERP, reportes de la app, eventos de
    seguridad y cuarentena) para empezar la demo en limpio. Requiere X-Device-Key."""
    _check_device_key(request, db, x_device_key)
    counts = {}
    for name, model, cond in [
        ("brigadas", BrigadeAssignment, None),
        ("documentos_erp", ErpTransaction, None),
        ("reportes_app", CitizenReport, CitizenReport.source == "app"),
        ("eventos_seguridad", SecurityEvent, None),
        ("cuarentena", QuarantinedReading, None),
    ]:
        stmt = model.__table__.delete()
        counts[name] = db.execute(stmt.where(cond) if cond is not None else stmt).rowcount
    for n in db.scalars(select(Node).where(Node.status == "mantenimiento_programado")).all():
        n.status = "sin_datos" if n.sim_offline else "activo"
    db.commit()
    dashboard_cache.invalidate()
    return {"reset": True, "eliminados": counts}


@router.get("/security/events", tags=["seguridad"], dependencies=[Depends(require_ready)])
def security_events(limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(select(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(limit)).all()
    return [{"ts": iso_utc(e.ts), "kind": e.kind, "severity": e.severity, "source_ip": e.source_ip, "detail": e.detail}
            for e in rows]


@router.get("/ops", tags=["operación"], dependencies=[Depends(require_ready)])
def ops(db: Session = Depends(get_db)):
    """Vista de operación: telemetría en vivo, cuarentena, nodos sin datos, ERP y seguridad."""
    now = utcnow()
    names = {a.id: a.name for a in db.scalars(select(Area)).all()}
    nodes = db.scalars(select(Node)).all()
    area_of = {n.id: n.area_id for n in nodes}
    cut = now - timedelta(hours=48)
    offline = sorted((n for n in nodes if n.sim_offline or not n.last_seen or n.last_seen < cut),
                     key=lambda n: n.last_seen or now)
    readings = db.scalars(select(Reading).order_by(Reading.id.desc()).limit(14)).all()
    quarantine = db.scalars(select(QuarantinedReading).order_by(QuarantinedReading.id.desc()).limit(6)).all()
    count = lambda model, col, since: db.scalar(select(func.count()).select_from(model).where(col >= since)) or 0  # noqa: E731
    return {
        "generated_at": iso_utc(now),
        "ingest": {
            "readings_last_min": count(Reading, Reading.ts, now - timedelta(seconds=60)),
            "readings_24h": count(Reading, Reading.ts, now - timedelta(hours=24)),
            "quarantined_24h": count(QuarantinedReading, QuarantinedReading.ts, now - timedelta(hours=24)),
            "security_24h": count(SecurityEvent, SecurityEvent.ts, now - timedelta(hours=24)),
            "simulator": app_state.simulator.running if app_state.simulator else False,
            "simulator_interval_s": settings.simulator_interval,
        },
        "telemetry": [reading_payload(r, names.get(area_of.get(r.node_id, ""), "")) for r in readings],
        "quarantine": [{"ts": iso_utc(q.ts), "node_id": q.node_id, "reason": q.reason} for q in quarantine],
        "offline_nodes": [{"id": n.id, "area": names.get(n.area_id), "last_seen": iso_utc(n.last_seen),
                           "hours": int((now - n.last_seen).total_seconds() // 3600) if n.last_seen else None,
                           "status": n.status, "battery_v": n.battery_v} for n in offline],
        "erp": [erp.tx_payload(t) for t in db.scalars(select(ErpTransaction).order_by(ErpTransaction.id.desc()).limit(12)).all()],
        "security": [{"ts": iso_utc(e.ts), "kind": e.kind, "severity": e.severity, "source_ip": e.source_ip,
                      "detail": e.detail} for e in db.scalars(select(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(8)).all()],
    }
