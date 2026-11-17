"""Modelo de datos persistente de Sentinela Aedes.

Tablas:
- areas: catálogo geográfico (estado, municipios, colonias de Mérida).
- nodes: ovitrampas IoT.
- readings: telemetría de los nodos (conteo diario de huevecillos y microclima).
- quarantined_readings: lecturas rechazadas por valores imposibles o anómalos.
- weather_daily: clima diario por área (Open-Meteo).
- cases_weekly: casos probables/confirmados por semana epidemiológica.
- citizen_reports: reportes ciudadanos de criaderos.
- brigade_assignments: brigadas asignadas desde el tablero.
- erp_transactions: bitácora de documentos enviados al ERP (simulado).
- security_events: eventos de seguridad (fuente para reglas SIEM).
- model_audit: auditoría de sesgos del modelo por tipo de zona.
- meta: llave/valor para estado interno (fechas de carga, etc.).
"""
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

# BIGINT autoincremental en Postgres, INTEGER en SQLite (requisito de ROWID).
BigId = BigInteger().with_variant(Integer(), "sqlite")


class Area(Base):
    __tablename__ = "areas"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # ej. col:mulsay, mun:merida
    kind: Mapped[str] = mapped_column(String(12), index=True)  # estado | municipio | colonia
    slug: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    parent_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    inegi_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    grid_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grid_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    marginacion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vulnerabilidad: Mapped[float | None] = mapped_column(Float, nullable=True)  # % viviendas con tambos
    viviendas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    turistico: Mapped[bool] = mapped_column(Boolean, default=False)


class Node(Base):
    __tablename__ = "nodes"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)  # OVI-0147
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id"), index=True)
    municipio_id: Mapped[str] = mapped_column(ForeignKey("areas.id"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    connectivity: Mapped[str] = mapped_column(String(12))  # LoRaWAN | NB-IoT
    firmware: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(24), default="activo")
    sim_offline: Mapped[bool] = mapped_column(Boolean, default=False)
    report_hour: Mapped[int] = mapped_column(Integer, default=6)
    factor: Mapped[float] = mapped_column(Float, default=1.0)  # productividad relativa de la trampa (simulación)
    latent: Mapped[float] = mapped_column(Float, default=0.5)  # propensión a ser positiva (simulación)
    installed_on: Mapped[date] = mapped_column(Date)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    battery_v: Mapped[float | None] = mapped_column(Float, nullable=True)


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC sin zona
    day: Mapped[date] = mapped_column(Date, index=True)  # fecha local (Mérida)
    kind: Mapped[str] = mapped_column(String(8))  # huevos | clima
    eggs_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eggs_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="device")  # seed | sim | device

    __table_args__ = (Index("ix_readings_kind_day", "kind", "day"),)


class QuarantinedReading(Base):
    __tablename__ = "quarantined_readings"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    node_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    reason: Mapped[str] = mapped_column(String(200))
    payload: Mapped[str] = mapped_column(Text)


class WeatherDaily(Base):
    __tablename__ = "weather_daily"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    precip_mm: Mapped[float] = mapped_column(Float)
    tmin: Mapped[float] = mapped_column(Float)
    tmax: Mapped[float] = mapped_column(Float)
    is_forecast: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20))  # open-meteo | simulado

    __table_args__ = (UniqueConstraint("area_id", "day", name="uq_weather_area_day"),)


class CasesWeekly(Base):
    __tablename__ = "cases_weekly"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    probable: Mapped[int] = mapped_column(Integer)
    confirmed: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))  # DGE | simulado

    __table_args__ = (UniqueConstraint("area_id", "year", "week", name="uq_cases_area_week"),)


class CitizenReport(Base):
    __tablename__ = "citizen_reports"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    folio: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    has_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12))  # validado | pendiente | descartado
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    source: Mapped[str] = mapped_column(String(10))  # seed | sim | app
    erp_folio: Mapped[str | None] = mapped_column(String(24), nullable=True)


class BrigadeAssignment(Base):
    __tablename__ = "brigade_assignments"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    risk_p: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(12))
    horizon_weeks: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="asignada")
    erp_folio: Mapped[str | None] = mapped_column(String(24), nullable=True)


class ErpTransaction(Base):
    __tablename__ = "erp_transactions"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    folio: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True)
    doc_type: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(String(240))
    area_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[str] = mapped_column(Text)
    ack: Mapped[str | None] = mapped_column(Text, nullable=True)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(10))  # baja | media | alta
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str] = mapped_column(String(300))


class ModelAudit(Base):
    __tablename__ = "model_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(40))
    segment: Mapped[str] = mapped_column(String(80))
    sensitivity: Mapped[float] = mapped_column(Float)
    false_alarm_rate: Mapped[float] = mapped_column(Float)


class Meta(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
