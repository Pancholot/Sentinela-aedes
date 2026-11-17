"""Ingesta de clima REAL desde la API pública de Open-Meteo.

Una sola petición trae, para cada municipio y colonia, la lluvia diaria y las
temperaturas mínima/máxima de los últimos 92 días y el pronóstico de 16 días.
Si la API no responde, se rellenan los días faltantes con clima simulado
(marcado como fuente "simulado") para que el sistema no se detenga.
"""
import logging
import math
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from .config import settings
from .models import Area, WeatherDaily
from .seed import get_meta, set_meta
from . import simdata
from .timeutil import local_today, utcnow

log = logging.getLogger("sentinela.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
PAST_DAYS = 92
FORECAST_DAYS = 16


def _fetch_open_meteo(areas: list[Area]) -> list[dict]:
    params = {
        "latitude": ",".join(f"{a.lat:.4f}" for a in areas),
        "longitude": ",".join(f"{a.lon:.4f}" for a in areas),
        "daily": "precipitation_sum,temperature_2m_min,temperature_2m_max",
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": "America/Merida",
    }
    resp = httpx.get(OPEN_METEO_URL, params=params, timeout=25.0)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


def refresh_weather(db: Session, force: bool = False) -> dict:
    """Actualiza el clima si no se ha hecho en las últimas N horas."""
    last = get_meta(db, "weather_fetched_at")
    if last and not force:
        age_h = (utcnow() - datetime.fromisoformat(last)).total_seconds() / 3600
        if age_h < settings.weather_refresh_hours:
            return {"status": "vigente", "source": get_meta(db, "weather_source")}
    areas = db.scalars(select(Area).order_by(Area.id)).all()
    today = local_today()
    if settings.weather_enabled:
        try:
            locs = _fetch_open_meteo(areas)
            rows = []
            for area, loc in zip(areas, locs):
                daily = loc["daily"]
                for i, day_s in enumerate(daily["time"]):
                    p = daily["precipitation_sum"][i]
                    tmin = daily["temperature_2m_min"][i]
                    tmax = daily["temperature_2m_max"][i]
                    if p is None or tmin is None or tmax is None:
                        continue
                    d = date.fromisoformat(day_s)
                    rows.append(dict(area_id=area.id, day=d, precip_mm=float(p), tmin=float(tmin),
                                     tmax=float(tmax), is_forecast=d > today, source="open-meteo"))
            if rows:
                first = min(r["day"] for r in rows)
                last_d = max(r["day"] for r in rows)
                db.execute(delete(WeatherDaily).where(WeatherDaily.day >= first, WeatherDaily.day <= last_d))
                db.execute(insert(WeatherDaily), rows)
                set_meta(db, "weather_fetched_at", utcnow().isoformat())
                set_meta(db, "weather_source", "open-meteo")
                db.commit()
                log.info("Clima real de Open-Meteo actualizado: %s registros", len(rows))
                return {"status": "actualizado", "source": "open-meteo", "rows": len(rows)}
        except Exception as exc:  # red caída, límite de la API, etc.
            db.rollback()
            log.warning("Open-Meteo no disponible (%s); se usa clima simulado", exc)
    n = ensure_synthetic(db, areas, today)
    set_meta(db, "weather_fetched_at", utcnow().isoformat())
    if not get_meta(db, "weather_source"):
        set_meta(db, "weather_source", "simulado")
    db.commit()
    return {"status": "simulado", "source": "simulado", "rows": n}


def ensure_synthetic(db: Session, areas: list[Area], today: date) -> int:
    start, end = today - timedelta(days=PAST_DAYS), today + timedelta(days=FORECAST_DAYS)
    have = {(a, d) for a, d in db.execute(
        select(WeatherDaily.area_id, WeatherDaily.day).where(WeatherDaily.day >= start, WeatherDaily.day <= end)
    ).all()}
    rows = []
    for area in areas:
        d = start
        while d <= end:
            if (area.id, d) not in have:
                r = simdata.rng_for("wx", area.id, d.isoformat())
                # Temporada de lluvias de junio a octubre.
                wet = 0.5 + 0.5 * math.cos((d.timetuple().tm_yday - 250) / 365 * 2 * math.pi)
                rain = r.expovariate(1 / (2 + 10 * wet)) if r.random() < 0.25 + 0.45 * wet else 0.0
                rows.append(dict(area_id=area.id, day=d, precip_mm=round(rain, 1),
                                 tmin=round(21.0 + 2.5 * wet + r.uniform(-1, 1), 1),
                                 tmax=round(30.0 + 3.0 * wet + r.uniform(-1, 1), 1),
                                 is_forecast=d > today, source="simulado"))
            d += timedelta(days=1)
    if rows:
        db.execute(insert(WeatherDaily), rows)
    return len(rows)
