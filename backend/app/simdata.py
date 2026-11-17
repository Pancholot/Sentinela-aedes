"""Generadores deterministas para la parte simulada de los datos.

Todo lo que aquí se genera corresponde a fuentes que todavía no existen
(red de ovitrampas IoT, reportes ciudadanos, casos por colonia) o que se
cargan opcionalmente de la DGE. Los generadores son deterministas (semilla
por nodo/día) para que la base se pueda reconstruir igual en cualquier
servidor y para que el "backfill" sea consistente.

Calibración de casos estatales: ~1,500 casos probables acumulados a la
semana 39 de 2026 y ~120 casos probables semanales hacia la semana 44,
en línea con las cifras públicas citadas en el reporte del equipo.
"""
import hashlib
import math
import random
from datetime import date

from .catalog import COLONIAS, MUNICIPIOS
from .timeutil import season_t

# Curva estacional de huevecillos: pico en la semana 47 de 2026.
EGG_PEAK = 47.0
EGG_SIGMA = 5.5
# La tendencia del catálogo corresponde a las semanas 42-45.
_B0 = math.exp(-(((42.0 - EGG_PEAK) / EGG_SIGMA) ** 2))
_B3 = math.exp(-(((45.0 - EGG_PEAK) / EGG_SIGMA) ** 2))

# Curva estatal de casos probables por semana.
CASE_BASE = 22.0
CASE_AMP = 104.0
CASE_PEAK = 47.0
CASE_SIGMA = 14.4
STATE_REST_SHARE = 0.15  # municipios fuera del piloto
CONFIRM_RATE = 0.035  # ~51 confirmados por ~1,500 probables


def unit(*keys) -> float:
    """Número pseudoaleatorio estable en [0, 1) a partir de llaves."""
    h = hashlib.md5("|".join(str(k) for k in keys).encode()).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


def rng_for(*keys) -> random.Random:
    return random.Random(int(unit(*keys) * 1e15))


def poisson(lam: float, rng: random.Random) -> int:
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def binomial(n: int, p: float, rng: random.Random) -> int:
    return sum(1 for _ in range(n) if rng.random() < p)


def egg_bell(t: float) -> float:
    return math.exp(-(((t - EGG_PEAK) / EGG_SIGMA) ** 2))


class EggProfile:
    """Nivel esperado de huevecillos por trampa por semana y positividad (IPO)."""

    def __init__(self, trend: tuple[float, ...], ipo_now: float, crd_now: float = 0.0):
        t0, t3 = float(trend[0]), float(trend[-1])
        self.amp = max(0.0, (t3 - t0) / (_B3 - _B0))
        self.base = max(0.5, t3 - self.amp * _B3)
        self.level_now = self.base + self.amp * _B3
        self.ipo_now = float(ipo_now)
        self.crd_now = float(crd_now)

    def level(self, d: date) -> float:
        return self.base + self.amp * egg_bell(season_t(d))

    def ipo(self, d: date) -> float:
        ratio = self.level(d) / max(self.level_now, 0.5)
        return min(92.0, max(4.0, self.ipo_now * math.sqrt(ratio)))

    def criaderos_per_day(self, d: date) -> float:
        return self.crd_now * self.level(d) / max(self.level_now, 0.5) / 7.0


def _build_profiles() -> dict[str, EggProfile]:
    profiles: dict[str, EggProfile] = {}
    for slug, _n, _r, _c, _la, _lo, ipo, crd, trend, _v, _viv in COLONIAS:
        profiles[f"col:{slug}"] = EggProfile(trend, ipo, crd)
    for m in MUNICIPIOS:
        slug, eggs, ipo = m[0], m[12], m[13]
        if eggs is None or slug == "merida":
            continue
        tilt = m[14]
        start = eggs * (1.0 - 0.45 * max(0.0, tilt + 0.25))
        profiles[f"mun:{slug}"] = EggProfile((start, 0, 0, eggs), ipo, crd_now=1.5 + 6 * max(0.0, tilt))
    return profiles


PROFILES = _build_profiles()


def daily_egg_delta(node_id: str, area_id: str, factor: float, latent: float, d: date) -> int:
    """Incremento diario de huevecillos de un nodo (conteo en el borde).

    Cada trampa tiene una propensión fija (`latent`): es positiva mientras su
    propensión esté por debajo del IPO esperado del área, de modo que la
    positividad sube o baja de forma gradual con la temporada. Las trampas
    positivas reciben huevecillos casi todos los días."""
    prof = PROFILES[area_id]
    ipo = prof.ipo(d) / 100.0
    if latent >= ipo:
        return 0
    rng = rng_for("eggs", node_id, d.isoformat())
    lam = prof.level(d) * factor / ipo / 7.0
    return poisson(lam, rng)


def state_cases_mean(t: float) -> float:
    return CASE_BASE + CASE_AMP * math.exp(-(((t - CASE_PEAK) / CASE_SIGMA) ** 2))


def _tilt_factor(tilt: float, t: float) -> float:
    return math.exp(tilt * max(0.0, t - 36.0) / 8.0)


def municipio_cases_mean(slug: str, t: float) -> float:
    m = next(x for x in MUNICIPIOS if x[0] == slug)
    return m[9] * state_cases_mean(t) * _tilt_factor(m[14], t)


_COL_HEAT = {c[0]: float(c[8][-1]) for c in COLONIAS}
_COL_HEAT_SUM = sum(_COL_HEAT.values())


def colonia_cases_mean(slug: str, t: float) -> float:
    c = next(x for x in COLONIAS if x[0] == slug)
    share = 0.6 * _COL_HEAT[slug] / _COL_HEAT_SUM
    growth = math.log(max(c[8][-1], 1) / max(c[8][0], 1)) / 2.0
    return share * municipio_cases_mean("merida", t) * _tilt_factor(growth, t)


def weekly_cases(area_id: str, year: int, week: int, t: float) -> tuple[int, int]:
    kind, slug = area_id.split(":", 1)
    if kind == "edo":
        # Estado = suma de los municipios del piloto + resto del estado.
        prob = conf = 0
        for m in MUNICIPIOS:
            p, c = weekly_cases(f"mun:{m[0]}", year, week, t)
            prob += p
            conf += c
        rng = rng_for("cases", area_id, year, week)
        rest = poisson(STATE_REST_SHARE * state_cases_mean(t), rng)
        return prob + rest, conf + binomial(rest, CONFIRM_RATE, rng)
    mean = municipio_cases_mean(slug, t) if kind == "mun" else colonia_cases_mean(slug, t)
    rng = rng_for("cases", area_id, year, week)
    prob = poisson(mean, rng)
    return prob, binomial(prob, CONFIRM_RATE, rng)
