"""Procesamiento analítico: indicadores (KPIs), riesgo de brote y pronóstico.

Todo se calcula en el servidor a partir de la base de datos:
- Índices entomológicos por ventana móvil de 7 días (huevecillos por trampa e
  IPO = % de ovitrampas positivas) a partir de la telemetría.
- Clima real (Open-Meteo): lluvia de 14 días, lluvia con rezago de 3 a 5
  semanas y temperatura mínima promedio.
- Riesgo de brote por colonia y por municipio a 1, 2 y 4 semanas: modelo
  logístico con coeficientes ajustados fuera de línea (prototipo del modelo
  de gradient boosting descrito en el reporte). Se explica con la
  contribución de cada variable.
- Pronóstico estatal de casos probables a 1-4 semanas: tendencia log-lineal
  de los casos combinada con el crecimiento del índice de huevecillos
  (indicador adelantado), amortiguada, con intervalo de confianza de 90 %.
"""
import math
import threading
import time
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalog import COLONIAS, DRIVERS_COLONIA, DRIVERS_MUNICIPIO, MARG_ORD
from .config import settings
from .db import db_kind
from .models import (
    Area,
    BrigadeAssignment,
    CasesWeekly,
    CitizenReport,
    ModelAudit,
    Node,
    QuarantinedReading,
    Reading,
    WeatherDaily,
)
from .seed import get_meta
from .timeutil import epi_week, iso_utc, last_complete_week, local_today, shift_week, utcnow

LEVELS = ["bajo", "moderado", "alto", "brote"]
HORIZONS = [1, 2, 4]
WEIGHT_LABELS = ["peso alto", "peso medio", "peso bajo"]
ONLINE_HOURS = 48

# --- Coeficientes del modelo de riesgo ---
# Ajustados fuera de línea por mínimos cuadrados regularizados (ridge hacia
# pesos a priori, pesos de variables >= 0) sobre el logit de los niveles de
# riesgo definidos por el equipo para el prototipo. Error medio: ~4 puntos
# porcentuales en colonias y ~7 en municipios. Las variables se centran en un
# valor de referencia, así su contribución explica el riesgo de cada área.
COEF_COL = {
    "intercept": -2.0613, "eggs": 0.0242, "growth": 0.2094, "ipo": 0.0228,
    "crd": 0.0179, "rain": 0.006, "heat": 0.20, "cases": 0.0153, "vulner": 0.0063,
    "vecina": 0.5,
}
H_OFF_COL = [0.0, 0.5928, 1.0359]
H_GROW_COL = [0.0, 0.0, 0.2244]

COEF_MUN = {
    "intercept": -1.4027, "cases": 0.4383, "cases_growth": 0.3411, "eggs": 0.0173,
    "ipo": 0.0148, "rain": 0.004, "heat": 0.15, "marg": 0.2378, "mov": 0.12,
    "vecina": 1.5,
}
H_OFF_MUN = [0.0, 0.4987, 0.9083]
H_GROW_MUN = [0.0, 0.0, 0.0569]


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def level_of(p: float) -> int:
    return 0 if p < 25 else 1 if p < 50 else 2 if p < 75 else 3


# ---------------------------------------------------------------- consultas

def _egg_windows(db: Session, nodes: list[Node]) -> dict:
    """Huevecillos/trampa/semana e IPO por colonia, municipio y estado en 4
    ventanas móviles de 7 días (0 = últimos 7 días)."""
    today = local_today()
    by_key: dict[str, list[list[tuple[int, int]]]] = defaultdict(lambda: [[] for _ in range(4)])
    node_keys = {n.id: {n.area_id, n.municipio_id, "edo:yucatan"} for n in nodes}
    start_all = today - timedelta(days=27)
    rows = db.execute(
        select(Reading.node_id, Reading.day, func.sum(Reading.eggs_delta), func.count())
        .where(Reading.kind == "huevos", Reading.day >= start_all, Reading.day <= today)
        .group_by(Reading.node_id, Reading.day)
    ).all()
    per_node: dict[str, list[list[int]]] = defaultdict(lambda: [[0, 0] for _ in range(4)])
    for node_id, day, s, _c in rows:
        k = (today - day).days // 7
        if 0 <= k < 4:
            acc = per_node[node_id][k]
            acc[0] += int(s or 0)
            acc[1] += 1
    for node_id, wins in per_node.items():
        for key in node_keys.get(node_id, ()):
            for k in range(4):
                if wins[k][1] > 0:
                    by_key[key][k].append((wins[k][0], wins[k][1]))
    out = {}
    for key, wins in by_key.items():
        eggs, ipo = [], []
        for samples in wins:
            if samples:
                eggs.append(sum(s / n * 7 for s, n in samples) / len(samples))
                ipo.append(100.0 * sum(1 for s, _ in samples if s > 0) / len(samples))
            else:
                eggs.append(None)
                ipo.append(None)
        out[key] = {"eggs": eggs, "ipo": ipo}
    return out


def _weather_features(db: Session) -> dict[str, dict]:
    today = local_today()
    rows = db.execute(
        select(WeatherDaily.area_id, WeatherDaily.day, WeatherDaily.precip_mm, WeatherDaily.tmin, WeatherDaily.tmax)
        .where(WeatherDaily.day >= today - timedelta(days=35), WeatherDaily.day <= today - timedelta(days=1))
    ).all()
    acc: dict[str, dict] = defaultdict(lambda: {"rain14": 0.0, "rain_lag": 0.0, "tmin": [], "tmax": []})
    for area_id, day, p, tmin, tmax in rows:
        age = (today - day).days
        a = acc[area_id]
        if age <= 14:
            a["rain14"] += p
            a["tmin"].append(tmin)
            a["tmax"].append(tmax)
        if 21 <= age <= 35:
            a["rain_lag"] += p
    out = {}
    for area_id, a in acc.items():
        out[area_id] = {
            "rain14": round(a["rain14"], 1), "rain_lag": round(a["rain_lag"], 1),
            "tmin14": round(sum(a["tmin"]) / len(a["tmin"]), 1) if a["tmin"] else 22.0,
            "tmax14": round(sum(a["tmax"]) / len(a["tmax"]), 1) if a["tmax"] else 31.0,
        }
    return out


def _weeks_back(n: int) -> list[tuple[int, int]]:
    lw = last_complete_week()
    return [shift_week(*lw, -k) for k in range(n)]  # [más reciente, ...]


def _cases(db: Session, weeks: list[tuple[int, int]]) -> dict[str, dict[tuple[int, int], tuple[int, int, str]]]:
    years = sorted({y for y, _ in weeks})
    wanted = set(weeks)
    rows = db.execute(
        select(CasesWeekly.area_id, CasesWeekly.year, CasesWeekly.week, CasesWeekly.probable,
               CasesWeekly.confirmed, CasesWeekly.source)
        .where(CasesWeekly.year.in_(years))
    ).all()
    out: dict[str, dict] = defaultdict(dict)
    for area_id, y, w, p, c, src in rows:
        if (y, w) in wanted:
            out[area_id][(y, w)] = (p, c, src)
    return out


# ----------------------------------------------------------------- modelos

def _neighbors(items: list[dict]) -> dict[str, list[str]]:
    out = {}
    for a in items:
        out[a["key"]] = [b["key"] for b in items if b is not a
                         and abs(b["gr"] - a["gr"]) <= 1 and abs(b["gc"] - a["gc"]) <= 1]
    return out


def _apply_neighbors(items: list[dict], coef: float, drivers_txt: dict) -> None:
    """Segunda pasada: el riesgo de las áreas vecinas se suma como variable."""
    nb = _neighbors(items)
    base_p2 = {a["key"]: sigmoid(a["z"][1]) for a in items}
    for a in items:
        mx = max((base_p2[k] for k in nb[a["key"]]), default=0.0)
        contrib = coef * max(0.0, mx - 0.55)
        a["contrib"]["vecina"] = contrib
        a["z"] = [z + contrib for z in a["z"]]
    for a in items:
        a["p"] = [int(round(100 * sigmoid(z))) for z in a["z"]]
        top = sorted(a["contrib"].items(), key=lambda kv: kv[1], reverse=True)[:3]
        a["drivers"] = [{"key": k, "text": drivers_txt[k], "weight": WEIGHT_LABELS[i]} for i, (k, _v) in enumerate(top)]


def _colonia_risk(f: dict) -> tuple[list[float], dict]:
    c = COEF_COL
    growth = math.log((f["eggs"] + 3) / (f["eggs_w3"] + 3))
    contrib = {
        "huevos": c["eggs"] * (f["eggs"] - 15) + c["growth"] * growth,
        "ipo": c["ipo"] * (f["ipo"] - 30),
        "criaderos": c["crd"] * (f["crd"] - 2),
        "lluvia": c["rain"] * (f["rain_lag"] - 60),
        "calor": c["heat"] * (f["tmin14"] - 22),
        "casos": c["cases"] * (f["cases4"] - 3),
        "vulner": c["vulner"] * (f["vulner"] - 20),
    }
    base = c["intercept"] + sum(contrib.values())
    z = [base + H_OFF_COL[h] + H_GROW_COL[h] * growth for h in range(3)]
    return z, contrib


def _municipio_risk(f: dict) -> tuple[list[float], dict]:
    c = COEF_MUN
    growth = math.log((f["cases4"] + 2) / (f["cases_prev4"] + 2))
    contrib = {
        "casos": c["cases"] * (math.log1p(f["cases4"]) - 2.5) + c["cases_growth"] * growth,
        "huevos": c["eggs"] * (f["eggs"] - 15) if f["eggs"] is not None else 0.0,
        "ipo": c["ipo"] * (f["ipo"] - 30) if f["ipo"] is not None else 0.0,
        "lluvia": c["rain"] * (f["rain_lag"] - 60),
        "calor": c["heat"] * (f["tmin14"] - 22),
        "vulner": c["marg"] * (f["marg"] - 2),
        "mov": c["mov"] * (1.0 if f["turistico"] else 0.0),
    }
    base = c["intercept"] + sum(contrib.values())
    z = [base + H_OFF_MUN[h] + H_GROW_MUN[h] * growth for h in range(3)]
    return z, contrib


def _forecast(state_obs: list[int], egg_growth: float) -> dict:
    y = [math.log(v + 1) for v in state_obs[-6:]]
    n = len(y)
    xs = list(range(n))
    xm, ym = sum(xs) / n, sum(y) / n
    sxx = sum((x - xm) ** 2 for x in xs) or 1.0
    slope = sum((x - xm) * (v - ym) for x, v in zip(xs, y)) / sxx
    fitted = [ym + slope * (x - xm) for x in xs]
    resid = [v - f for v, f in zip(y, fitted)]
    sigma = math.sqrt(sum(r * r for r in resid) / max(1, n - 2))
    rate = max(-0.3, min(0.3, 0.5 * slope + 0.5 * egg_growth))
    phi = 0.92
    level0 = math.exp(fitted[-1]) - 1
    mean, lo, hi = [], [], []
    for h in range(1, 5):
        cum = sum(phi ** i for i in range(h))
        m = level0 * math.exp(rate * cum)
        sd = math.sqrt(sigma * sigma * h + (0.05 * h) ** 2)
        mean.append(int(round(m)))
        lo.append(int(round(m * math.exp(-1.645 * sd))))
        hi.append(int(round(m * math.exp(1.645 * sd))))
    return {"mean": mean, "lo": lo, "hi": hi, "case_trend": round(slope, 4),
            "egg_growth": round(egg_growth, 4), "rate": round(rate, 4)}


# ------------------------------------------------------------- tablero

def compute_dashboard(db: Session) -> dict:
    now = utcnow()
    today = local_today()
    areas = {a.id: a for a in db.scalars(select(Area)).all()}
    nodes = db.scalars(select(Node)).all()
    online_cut = now - timedelta(hours=ONLINE_HOURS)
    eggs = _egg_windows(db, nodes)
    wx = _weather_features(db)
    weeks8 = _weeks_back(8)
    weeks11 = _weeks_back(11)
    cases = _cases(db, sorted(set(weeks8) | set(weeks11)))

    def cases_sum(area_id: str, wk: list[tuple[int, int]]) -> int:
        return sum(cases.get(area_id, {}).get(w, (0, 0, ""))[0] for w in wk)

    nodes_by: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for n in nodes:
        on = n.last_seen is not None and n.last_seen >= online_cut and not n.sim_offline
        # En el interior área = municipio; en Mérida el nodo cuenta en su colonia y en el municipio.
        for key in {n.area_id, n.municipio_id}:
            nodes_by[key][1] += 1
            nodes_by[key][0] += 1 if on else 0

    week_ago = now - timedelta(days=7)
    rep_rows = db.execute(
        select(CitizenReport.area_id, CitizenReport.status, CitizenReport.has_photo)
        .where(CitizenReport.created_at >= week_ago)
    ).all()
    crd_by = defaultdict(int)
    rep_total = rep_valid = 0
    for area_id, status, _photo in rep_rows:
        rep_total += 1
        if status == "validado":
            rep_valid += 1
            crd_by[area_id] += 1

    assigned = {}
    for a in db.scalars(select(BrigadeAssignment).where(BrigadeAssignment.created_at >= week_ago)
                        .order_by(BrigadeAssignment.created_at)).all():
        assigned[a.area_id] = {"folio": a.erp_folio, "created_at": iso_utc(a.created_at), "status": a.status}

    # ---- colonias
    cols = []
    for c in COLONIAS:
        key = f"col:{c[0]}"
        area = areas[key]
        e = eggs.get(key, {"eggs": [0, 0, 0, 0], "ipo": [0, 0, 0, 0]})
        ev = [v if v is not None else 0.0 for v in e["eggs"]]
        iv = [v if v is not None else 0.0 for v in e["ipo"]]
        w = wx.get(key, {"rain14": 0, "rain_lag": 0, "tmin14": 22, "tmax14": 31})
        f = {"eggs": ev[0], "eggs_w3": ev[3], "ipo": iv[0], "crd": crd_by[key], "rain_lag": w["rain_lag"],
             "tmin14": w["tmin14"], "cases4": cases_sum(key, weeks8[:4]), "vulner": area.vulnerabilidad or 20}
        z, contrib = _colonia_risk(f)
        cols.append({
            "key": key, "id": c[0], "name": area.name, "gr": area.grid_row, "gc": area.grid_col,
            "z": z, "contrib": contrib,
            "ipo": int(round(iv[0])), "ipo_prev": int(round(iv[1])), "eggs": int(round(ev[0])), "crd": crd_by[key],
            "rain": int(round(w["rain14"])), "rain_lag": int(round(w["rain_lag"])), "tmin": w["tmin14"],
            "trend": [int(round(v)) for v in reversed(ev)], "cases4": f["cases4"],
            "nodes": {"online": nodes_by[key][0], "total": nodes_by[key][1]},
            "viviendas": area.viviendas, "vulnerabilidad": area.vulnerabilidad,
            "assigned": key in assigned, "assignment": assigned.get(key),
        })
    _apply_neighbors(cols, COEF_COL["vecina"], DRIVERS_COLONIA)

    # ---- municipios
    muns = []
    for area in sorted((a for a in areas.values() if a.kind == "municipio"), key=lambda a: (a.grid_row, a.grid_col)):
        key = area.id
        e = eggs.get(key)
        iot = nodes_by[key][1] > 0
        w = wx.get(key, {"rain14": 0, "rain_lag": 0, "tmin14": 22, "tmax14": 31})
        c4 = cases_sum(key, weeks8[:4])
        cp4 = cases_sum(key, weeks8[4:])
        f = {"cases4": c4, "cases_prev4": cp4,
             "eggs": (e["eggs"][0] if e and e["eggs"][0] is not None else None) if iot else None,
             "ipo": (e["ipo"][0] if e and e["ipo"][0] is not None else None) if iot else None,
             "rain_lag": w["rain_lag"], "tmin14": w["tmin14"], "marg": MARG_ORD.get(area.marginacion or "Media", 2),
             "turistico": area.turistico}
        z, contrib = _municipio_risk(f)
        muns.append({
            "key": key, "id": area.slug, "name": area.name, "gr": area.grid_row, "gc": area.grid_col,
            "z": z, "contrib": contrib, "cases4": c4, "cases_prev4": cp4,
            "cases_txt": "menos de 5" if c4 < 5 else f"{c4:,}",
            "marg": area.marginacion, "iot": iot, "inegi": area.inegi_code,
            "nodes": {"online": nodes_by[key][0], "total": nodes_by[key][1]},
            "eggs": int(round(f["eggs"])) if f["eggs"] is not None else None,
            "ipo": int(round(f["ipo"])) if f["ipo"] is not None else None,
            "rain": int(round(w["rain14"])), "rain_lag": int(round(w["rain_lag"])), "tmin": w["tmin14"],
            "conf": "Alta" if iot else "Media (solo casos y clima)",
            "assigned": key in assigned, "assignment": assigned.get(key),
        })
    _apply_neighbors(muns, COEF_MUN["vecina"], DRIVERS_MUNICIPIO)

    # ---- pronóstico estatal
    obs_weeks = list(reversed(weeks11))
    state = cases.get("edo:yucatan", {})
    observed = [state.get(w, (0, 0, ""))[0] for w in obs_weeks]
    g = eggs.get("edo:yucatan", {"eggs": [0, 0, 0, 0]})["eggs"]
    egg_growth = math.log(((g[0] or 0) + 2) / ((g[3] or 0) + 2)) / 3.0
    fc = _forecast(observed, egg_growth)
    thr = settings.epidemic_threshold
    lw_y, lw_w = obs_weeks[-1]
    fc_weeks = [shift_week(lw_y, lw_w, h) for h in range(1, 5)]
    cross = next((i for i, v in enumerate(fc["mean"]) if v >= thr), None)
    sources = {s for area_c in cases.values() for (_p, _c, s) in area_c.values()}
    forecast = {
        "weeks": [w for _y, w in obs_weeks] + [w for _y, w in fc_weeks],
        "observed": observed, "mean": fc["mean"], "lo": fc["lo"], "hi": fc["hi"], "threshold": thr,
        "last_obs_week": lw_w, "cross_week": fc_weeks[cross][1] if cross is not None else None,
        "already_above": observed[-1] >= thr,
        "model": "Tendencia log-lineal de casos + crecimiento del índice de huevecillos (rezago), amortiguada",
        "params": {"case_trend": fc["case_trend"], "egg_growth": fc["egg_growth"], "rate": fc["rate"]},
    }

    # ---- KPIs
    edo_e = eggs.get("edo:yucatan", {"ipo": [0, 0, 0, 0]})
    ipo_now = edo_e["ipo"][0] or 0
    ipo_prev = edo_e["ipo"][1] or 0
    total_nodes = len(nodes)
    online_nodes = sum(1 for n in nodes if n.last_seen and n.last_seen >= online_cut and not n.sim_offline)
    rural = [n for n in nodes if n.municipio_id != "mun:merida"]
    rural_on = sum(1 for n in rural if n.last_seen and n.last_seen >= online_cut and not n.sim_offline)
    readings_24h = db.scalar(select(func.count()).select_from(Reading).where(Reading.ts >= now - timedelta(hours=24)))
    last_reading = db.scalar(select(func.max(Reading.ts)))
    quarantined_24h = db.scalar(select(func.count()).select_from(QuarantinedReading)
                                .where(QuarantinedReading.ts >= now - timedelta(hours=24)))
    audit = [{"label": a.segment, "v": int(round(a.sensitivity)), "far": a.false_alarm_rate, "period": a.period}
             for a in db.scalars(select(ModelAudit).order_by(ModelAudit.id)).all()]

    y, wk = epi_week(today)
    for item in cols + muns:
        item.pop("z", None)
        item["contrib"] = {k: round(v, 3) for k, v in item["contrib"].items()}

    return {
        "meta": {
            "generated_at": iso_utc(now), "epi_year": y, "epi_week": wk, "last_complete_week": lw_w,
            "db": db_kind(), "weather_source": get_meta(db, "weather_source", "simulado"),
            "weather_fetched_at": get_meta(db, "weather_fetched_at"),
            "cases_source": "DGE (datos abiertos)" if "DGE" in sources else "simulado (calibrado con cifras oficiales 2026)",
            "erp": settings.erp_name, "simulator": settings.simulator_enabled, "horizons": HORIZONS,
        },
        "colonias": cols,
        "municipios": muns,
        "forecast": forecast,
        "kpis": {
            "ipo": int(round(ipo_now)), "ipo_delta": int(round(ipo_now - ipo_prev)),
            "nodes_online": online_nodes, "nodes_total": total_nodes, "nodes_offline": total_nodes - online_nodes,
            "rural_online": rural_on, "rural_total": len(rural),
            "reports_validated": rep_valid, "reports_total": rep_total,
            "reports_valid_pct": int(round(100 * rep_valid / rep_total)) if rep_total else 0,
            "readings_24h": readings_24h or 0, "last_reading_at": iso_utc(last_reading),
            "quarantined_24h": quarantined_24h or 0,
            "cases4_municipios": sum(m["cases4"] for m in muns),
        },
        "audit": audit,
    }


class _Cache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self.value = None
        self.at = 0.0
        self.lock = threading.Lock()

    def get(self, db: Session) -> dict:
        with self.lock:
            if self.value is None or time.monotonic() - self.at > self.ttl:
                self.value = compute_dashboard(db)
                self.at = time.monotonic()
            return self.value

    def invalidate(self) -> None:
        with self.lock:
            self.value = None


dashboard_cache = _Cache(ttl=4.0)
