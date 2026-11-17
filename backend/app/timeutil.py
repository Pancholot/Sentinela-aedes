"""Utilidades de tiempo: hora local de Mérida y semanas epidemiológicas.

Las fechas/horas se guardan en la base como UTC sin zona; los días ("day")
se guardan en hora local de Mérida para agregar por día y por semana.
"""
from datetime import date, datetime, timedelta, timezone

from .config import LOCAL_TZ


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def local_today() -> date:
    return local_now().date()


def to_local_day(ts_utc_naive: datetime) -> date:
    return ts_utc_naive.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).date()


def local_to_utc_naive(d: date, hour: int, minute: int = 0) -> datetime:
    local = datetime(d.year, d.month, d.day, hour, minute, tzinfo=LOCAL_TZ)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def iso_utc(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


# --- Semanas epidemiológicas (criterio SINAVE/MMWR: inician en domingo; la
# semana 1 es la primera que tiene al menos 4 días del año nuevo) ---

def week1_start(year: int) -> date:
    jan1 = date(year, 1, 1)
    wd = (jan1.weekday() + 1) % 7  # domingo = 0
    start = jan1 - timedelta(days=wd)
    if wd > 3:
        start += timedelta(days=7)
    return start


def epi_week(d: date) -> tuple[int, int]:
    y = d.year
    if d >= week1_start(y + 1):
        return y + 1, 1
    if d < week1_start(y):
        y -= 1
    return y, (d - week1_start(y)).days // 7 + 1


def week_start(year: int, week: int) -> date:
    return week1_start(year) + timedelta(days=7 * (week - 1))


def shift_week(year: int, week: int, k: int) -> tuple[int, int]:
    return epi_week(week_start(year, week) + timedelta(days=7 * k))


def last_complete_week(today: date | None = None) -> tuple[int, int]:
    today = today or local_today()
    y, w = epi_week(today)
    return shift_week(y, w, -1)


def season_t(d: date) -> float:
    """Semana epidemiológica continua (float) contada desde la semana 1 de 2026."""
    return (d - week1_start(2026)).days / 7.0 + 1.0
