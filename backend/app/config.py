"""Configuración del backend, leída de variables de entorno.

En Render se definen en el panel (o en render.yaml). En local se usan los
valores por defecto: SQLite en ./sentinela.db y simulador encendido.
"""
import os
from datetime import timedelta, timezone
from pathlib import Path

_DEFAULT_SQLITE = "sqlite:///" + (Path(__file__).resolve().parent.parent / "sentinela.db").as_posix()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def normalize_db_url(url: str) -> str:
    """Render/Neon entregan 'postgres://...'; SQLAlchemy + psycopg 3 necesita
    'postgresql+psycopg://...'."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings:
    database_url: str = normalize_db_url(os.getenv("DATABASE_URL") or _DEFAULT_SQLITE)
    # Llave compartida que presentan los nodos/gateways al enviar telemetría.
    device_api_key: str = os.getenv("DEVICE_API_KEY", "dev-device-key")
    # Orígenes permitidos (URL de Vercel). "*" acepta cualquiera.
    cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
    # Simulador de flota IoT dentro del backend (telemetría continua).
    simulator_enabled: bool = _bool("SIMULATOR_ENABLED", True)
    simulator_interval: float = float(os.getenv("SIMULATOR_INTERVAL", "5"))
    # Clima real desde Open-Meteo (sin API key).
    weather_enabled: bool = _bool("WEATHER_ENABLED", True)
    weather_refresh_hours: float = float(os.getenv("WEATHER_REFRESH_HOURS", "6"))
    # Carga opcional de casos reales de la DGE (datos abiertos de dengue).
    dge_etl_enabled: bool = _bool("DGE_ETL_ENABLED", False)
    dge_url: str = os.getenv(
        "DGE_URL",
        "http://datosabiertos.salud.gob.mx/gobmx/salud/datos_abiertos/etv/datos_abiertos_dengue.zip",
    )
    # Umbral epidémico estatal (canal endémico simplificado, casos probables/semana).
    epidemic_threshold: int = int(os.getenv("EPIDEMIC_THRESHOLD", "150"))
    # Nombre del ERP destino (simulado).
    erp_name: str = os.getenv("ERP_NAME", "ERP institucional SSY (simulado)")


settings = Settings()

# Yucatán usa UTC-6 todo el año (México eliminó el horario de verano en 2022).
LOCAL_TZ = timezone(timedelta(hours=-6), "America/Merida")
