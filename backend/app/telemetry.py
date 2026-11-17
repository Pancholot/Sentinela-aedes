"""Ingesta y validación de telemetría de las ovitrampas IoT.

Reglas de calidad (del diseño del proyecto: "nodos con valores imposibles o
distintos a su histórico van a cuarentena"):
- Nodo desconocido → cuarentena + evento de seguridad.
- Valores físicamente imposibles (temperatura, humedad, batería, conteos) → cuarentena.
- Marca de tiempo en el futuro o con más de 7 días de atraso → cuarentena.
- Incremento de huevecillos muy por encima del histórico del nodo → cuarentena.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Node, QuarantinedReading, Reading, SecurityEvent
from .timeutil import epi_week, to_local_day, utcnow

log = logging.getLogger("sentinela.telemetry")


class ReadingIn(BaseModel):
    node_id: str = Field(..., max_length=40, examples=["OVI-0147"])
    ts: datetime | None = Field(None, description="Marca de tiempo ISO-8601; si falta se usa la hora del servidor")
    kind: Literal["huevos", "clima"] = "clima"
    eggs_count: int | None = Field(None, description="Huevecillos acumulados en la paleta (conteo en el borde)")
    eggs_delta: int | None = Field(None, description="Incremento respecto al conteo del día anterior")
    temp_c: float | None = None
    humidity: float | None = None
    battery_v: float | None = None
    rssi: int | None = None


class BatchIn(BaseModel):
    gateway_id: str | None = Field(None, max_length=40)
    readings: list[ReadingIn] = Field(..., min_length=1, max_length=500)


def _to_utc_naive(ts: datetime | None) -> datetime:
    if ts is None:
        return utcnow()
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def security_event(db: Session, kind: str, severity: str, detail: str, ip: str | None = None) -> None:
    db.add(SecurityEvent(ts=utcnow(), kind=kind, severity=severity, source_ip=ip, detail=detail[:300]))


def register_auth_failure(db: Session, ip: str | None, detail: str) -> None:
    """Registra un intento con llave inválida y aplica la regla de detección:
    5 o más fallos desde la misma IP en 60 s → evento de severidad alta."""
    security_event(db, "auth_fail", "media", detail, ip)
    db.flush()
    since = utcnow() - timedelta(seconds=60)
    n = db.scalar(select(func.count()).select_from(SecurityEvent).where(
        SecurityEvent.kind == "auth_fail", SecurityEvent.source_ip == ip, SecurityEvent.ts >= since))
    already = db.scalar(select(func.count()).select_from(SecurityEvent).where(
        SecurityEvent.kind == "brute_force", SecurityEvent.source_ip == ip, SecurityEvent.ts >= since))
    if n >= 5 and not already:
        security_event(db, "brute_force", "alta",
                       f"Regla SIEM SA-001: {n} intentos con llave de dispositivo inválida en 60 s desde {ip}", ip)
        log.warning("[SIEM] Posible fuerza bruta contra /api/telemetry desde %s (%s intentos/60 s)", ip, n)
    db.commit()


def _quarantine(db: Session, r: ReadingIn, reason: str) -> tuple[bool, str]:
    db.add(QuarantinedReading(node_id=r.node_id, ts=utcnow(), reason=reason,
                              payload=r.model_dump_json()))
    return False, reason


def ingest_reading(db: Session, r: ReadingIn, source: str = "device", ip: str | None = None) -> tuple[bool, str]:
    """Valida y guarda una lectura. Regresa (aceptada, motivo)."""
    node = db.get(Node, r.node_id)
    if node is None:
        security_event(db, "unknown_node", "media", f"Lectura de nodo no registrado {r.node_id!r}", ip)
        return _quarantine(db, r, "Nodo no registrado")
    ts = _to_utc_naive(r.ts)
    now = utcnow()
    if ts > now + timedelta(minutes=5):
        return _quarantine(db, r, "Marca de tiempo en el futuro")
    if ts < now - timedelta(days=7):
        return _quarantine(db, r, "Lectura con más de 7 días de atraso")
    checks = [
        (r.temp_c, 5, 50, "Temperatura fuera de rango físico"),
        (r.humidity, 0, 100, "Humedad fuera de rango"),
        (r.battery_v, 2.8, 4.5, "Voltaje de batería imposible"),
        (r.eggs_count, 0, 2000, "Conteo de huevecillos imposible"),
        (r.eggs_delta, 0, 800, "Incremento de huevecillos imposible"),
        (r.rssi, -140, 0, "RSSI fuera de rango"),
    ]
    for value, lo, hi, msg in checks:
        if value is not None and not (lo <= value <= hi):
            return _quarantine(db, r, f"{msg} ({value})")

    day = to_local_day(ts)
    eggs_delta = r.eggs_delta
    if r.kind == "huevos":
        if r.eggs_count is None and r.eggs_delta is None:
            return _quarantine(db, r, "Lectura de huevecillos sin conteo")
        prev = db.execute(
            select(Reading.day, Reading.eggs_count).where(Reading.node_id == node.id, Reading.kind == "huevos")
            .order_by(Reading.ts.desc()).limit(1)
        ).first()
        if eggs_delta is None:
            same_week = prev is not None and epi_week(prev.day) == epi_week(day)
            prev_count = (prev.eggs_count or 0) if same_week else 0
            eggs_delta = max(0, (r.eggs_count or 0) - prev_count)
        # Comparación contra el histórico del propio nodo (14 días).
        mean = db.scalar(select(func.avg(Reading.eggs_delta)).where(
            Reading.node_id == node.id, Reading.kind == "huevos", Reading.day >= day - timedelta(days=14)))
        if mean is not None and eggs_delta > max(60.0, 6.0 * float(mean) + 30.0):
            return _quarantine(db, r, f"Incremento anómalo vs. histórico del nodo ({eggs_delta} vs. media {float(mean):.1f})")

    db.add(Reading(node_id=node.id, ts=ts, day=day, kind=r.kind, eggs_count=r.eggs_count, eggs_delta=eggs_delta,
                   temp_c=r.temp_c, humidity=r.humidity, battery_v=r.battery_v, rssi=r.rssi, source=source))
    if node.last_seen is None or ts > node.last_seen:
        node.last_seen = ts
    if r.battery_v is not None:
        node.battery_v = r.battery_v
    if node.status == "sin_datos" and not node.sim_offline:
        node.status = "activo"
    return True, "ok"


def reading_payload(r: Reading, area_name: str) -> dict:
    from .timeutil import iso_utc
    return {
        "id": r.id, "node_id": r.node_id, "area": area_name, "kind": r.kind, "ts": iso_utc(r.ts),
        "eggs_count": r.eggs_count, "eggs_delta": r.eggs_delta, "temp_c": r.temp_c,
        "humidity": r.humidity, "battery_v": r.battery_v, "rssi": r.rssi, "source": r.source,
    }


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
