"""Siembra inicial de la base y "backfill" de series de tiempo.

- seed_if_empty: crea catálogo (estado, municipios, colonias), 400 nodos IoT
  y la auditoría del modelo, solo si la base está vacía.
- backfill_*: rellena lecturas diarias de huevecillos, reportes ciudadanos y
  casos semanales desde el último dato guardado hasta hoy. Así la demo se ve
  continua aunque el servidor gratuito haya estado dormido varios días.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from . import simdata
from .catalog import AUDITORIA, COLONIAS, ESTADO, MUNICIPIOS, VULNERABILIDAD_MUN
from .models import (
    Area,
    CasesWeekly,
    CitizenReport,
    Meta,
    ModelAudit,
    Node,
    Reading,
    WeatherDaily,
)
from .timeutil import (
    epi_week,
    last_complete_week,
    local_now,
    local_to_utc_naive,
    local_today,
    season_t,
    shift_week,
    to_local_day,
    utcnow,
    week_start,
)

log = logging.getLogger("sentinela.seed")

HISTORY_DAYS = 42  # 6 semanas de lecturas diarias por nodo
SEASON_START = (2026, 1)


def get_meta(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.get(Meta, key)
    return row.value if row else default


def set_meta(db: Session, key: str, value: str) -> None:
    row = db.get(Meta, key)
    if row:
        row.value = value
    else:
        db.add(Meta(key=key, value=value))


def seed_if_empty(db: Session) -> bool:
    if db.scalar(select(func.count()).select_from(Area)):
        return False
    log.info("Base vacía: sembrando catálogo y nodos IoT…")
    slug, name, code, lat, lon = ESTADO
    db.add(Area(id=f"edo:{slug}", kind="estado", slug=slug, name=name, inegi_code=code, lat=lat, lon=lon))
    for m in MUNICIPIOS:
        (mslug, mname, mcode, gr, gc, lat, lon, marg, tur, *_rest) = m
        db.add(Area(
            id=f"mun:{mslug}", kind="municipio", slug=mslug, name=mname, parent_id="edo:yucatan",
            inegi_code=mcode, grid_row=gr, grid_col=gc, lat=lat, lon=lon, marginacion=marg,
            vulnerabilidad=VULNERABILIDAD_MUN[marg], turistico=tur,
            viviendas=None,
        ))
    for c in COLONIAS:
        (cslug, cname, gr, gc, lat, lon, _ipo, _crd, _trend, vul, viv) = c
        db.add(Area(
            id=f"col:{cslug}", kind="colonia", slug=cslug, name=cname, parent_id="mun:merida",
            grid_row=gr, grid_col=gc, lat=lat, lon=lon, marginacion=None,
            vulnerabilidad=vul, viviendas=viv, turistico=False,
        ))
    db.flush()
    _create_nodes(db)
    for period, segment, sens, far in AUDITORIA:
        db.add(ModelAudit(period=period, segment=segment, sensitivity=sens, false_alarm_rate=far))
    set_meta(db, "seeded_at", utcnow().isoformat())
    set_meta(db, "cases_source", "simulado")
    db.commit()
    return True


def _stratified(rng, n: int) -> list[float]:
    """Propensiones repartidas de forma uniforme dentro del área (muestreo estratificado)."""
    vals = [(k + rng.uniform(0.2, 0.8)) / n for k in range(n)]
    rng.shuffle(vals)
    return [round(v, 4) for v in vals]


def _create_nodes(db: Session) -> None:
    rng = simdata.random.Random(2026)
    now = utcnow()
    idx = 1
    nodes: list[Node] = []
    # Mérida: 15 ovitrampas IoT por colonia piloto (300), LoRaWAN.
    merida_ids = list(range(1, 301))
    offline_merida = set(rng.sample(merida_ids, 12))
    for c in COLONIAS:
        latents = _stratified(rng, 15)
        for k in range(15):
            nodes.append(Node(
                id=f"OVI-{idx:04d}", area_id=f"col:{c[0]}", municipio_id="mun:merida",
                lat=c[4] + rng.uniform(-0.006, 0.006), lon=c[5] + rng.uniform(-0.006, 0.006),
                connectivity="LoRaWAN", firmware="v1.4.2", sim_offline=idx in offline_merida,
                report_hour=rng.randint(5, 8), factor=round(rng.lognormvariate(0, 0.15), 3), latent=latents[k],
                installed_on=date(2026, 6, 1) + timedelta(days=rng.randint(0, 60)),
            ))
            idx += 1
    # Municipios del interior: 10 por municipio con nodos (100), NB-IoT/gateway.
    for m in MUNICIPIOS:
        mslug, n_nodes, n_off = m[0], m[10], m[11]
        if mslug == "merida" or n_nodes == 0:
            continue
        off = set(rng.sample(range(n_nodes), n_off))
        latents = _stratified(rng, n_nodes)
        for k in range(n_nodes):
            nodes.append(Node(
                id=f"OVI-{idx:04d}", area_id=f"mun:{mslug}", municipio_id=f"mun:{mslug}",
                lat=m[5] + rng.uniform(-0.02, 0.02), lon=m[6] + rng.uniform(-0.02, 0.02),
                connectivity="NB-IoT", firmware="v1.4.2", sim_offline=k in off,
                report_hour=rng.randint(5, 8), factor=round(rng.lognormvariate(0, 0.15), 3), latent=latents[k],
                installed_on=date(2026, 8, 1) + timedelta(days=rng.randint(0, 30)),
            ))
            idx += 1
    for n in nodes:
        if n.sim_offline:
            # Falla técnica simulada: sin datos desde hace 2 a 5 días.
            n.last_seen = now - timedelta(hours=rng.randint(50, 120))
            n.status = "sin_datos"
            n.battery_v = round(rng.uniform(3.2, 3.5), 2)
    db.add_all(nodes)


def _weather_index(db: Session, start: date, end: date) -> dict[tuple[str, date], tuple[float, float]]:
    rows = db.execute(
        select(WeatherDaily.area_id, WeatherDaily.day, WeatherDaily.tmin, WeatherDaily.tmax)
        .where(WeatherDaily.day >= start, WeatherDaily.day <= end)
    ).all()
    return {(a, d): (tmin, tmax) for a, d, tmin, tmax in rows}


def backfill_readings(db: Session) -> int:
    """Genera la lectura diaria de huevecillos de cada nodo en línea que falte."""
    today = local_today()
    hour = local_now().hour
    first_day = today - timedelta(days=HISTORY_DAYS - 1)
    last_rows = db.execute(
        select(Reading.node_id, func.max(Reading.day)).where(Reading.kind == "huevos").group_by(Reading.node_id)
    ).all()
    last_day = {nid: d for nid, d in last_rows}
    nodes = db.scalars(select(Node)).all()
    weather = _weather_index(db, first_day, today)

    # Conteo acumulado de la semana para continuar la serie de cada nodo.
    prev_counts: dict[str, tuple[date, int]] = {}
    if last_day:
        rows = db.execute(
            select(Reading.node_id, Reading.day, Reading.eggs_count)
            .where(Reading.kind == "huevos", Reading.day >= today - timedelta(days=HISTORY_DAYS + 7))
            .order_by(Reading.day)
        ).all()
        for nid, d, cnt in rows:
            prev_counts[nid] = (d, cnt or 0)

    batch: list[dict] = []
    total = 0
    for node in nodes:
        start = last_day.get(node.id)
        start = (start + timedelta(days=1)) if start else first_day
        start = max(start, first_day)
        end = today if hour >= node.report_hour else today - timedelta(days=1)
        if node.sim_offline and node.last_seen:
            end = min(end, to_local_day(node.last_seen) - timedelta(days=1))
        if start > end:
            continue
        prev_day, count = prev_counts.get(node.id, (None, 0))
        d = start
        last_ts = None
        while d <= end:
            # La paleta se cambia cada semana epidemiológica (domingo).
            if prev_day is None or epi_week(prev_day) != epi_week(d):
                count = 0
            delta = simdata.daily_egg_delta(node.id, node.area_id, node.factor, node.latent, d)
            count += delta
            r = simdata.rng_for("clim", node.id, d.isoformat())
            tmin, _tmax = weather.get((node.area_id, d)) or weather.get((node.municipio_id, d)) or (22.5, 31.0)
            ts = local_to_utc_naive(d, node.report_hour, int(r.random() * 59))
            batch.append(dict(
                node_id=node.id, ts=ts, day=d, kind="huevos", eggs_count=count, eggs_delta=delta,
                temp_c=round(tmin + 1.0 + r.uniform(0, 2.0), 1), humidity=round(r.uniform(74, 96), 1),
                battery_v=round(r.uniform(3.75, 4.1), 2), rssi=int(r.uniform(-118, -72)), source="seed",
            ))
            prev_day, last_ts = d, ts
            d += timedelta(days=1)
        if last_ts and not node.sim_offline:
            if node.last_seen is None or last_ts > node.last_seen:
                node.last_seen = last_ts
                node.battery_v = batch[-1]["battery_v"]
        if len(batch) >= 5000:
            db.execute(insert(Reading), batch)
            total += len(batch)
            batch = []
    if batch:
        db.execute(insert(Reading), batch)
        total += len(batch)
    db.commit()
    if total:
        log.info("Backfill: %s lecturas diarias de huevecillos generadas", total)
    return total


def backfill_reports(db: Session) -> int:
    """Reportes ciudadanos simulados por día (criaderos)."""
    today = local_today()
    until_raw = get_meta(db, "reports_until")
    start = date.fromisoformat(until_raw) + timedelta(days=1) if until_raw else today - timedelta(days=20)
    start = max(start, today - timedelta(days=20))
    if start > today:
        return 0
    frac_today = local_now().hour / 24.0
    rows = []
    d = start
    while d <= today:
        scale = frac_today if d == today else 1.0
        for area_id, prof in simdata.PROFILES.items():
            rng = simdata.rng_for("crd", area_id, d.isoformat())
            n = simdata.poisson(prof.criaderos_per_day(d) * scale, rng)
            for k in range(n):
                has_photo = rng.random() < 0.95
                status = "validado" if (has_photo and rng.random() < 0.93) else ("pendiente" if rng.random() < 0.6 else "descartado")
                hour = rng.randint(7, 21) if d != today else rng.randint(7, max(7, local_now().hour))
                rows.append(dict(
                    folio=None, area_id=area_id, description="Reporte ciudadano (app / WhatsApp)",
                    has_photo=has_photo, status=status, created_at=local_to_utc_naive(d, min(hour, 23), rng.randint(0, 59)),
                    source="seed",
                ))
        d += timedelta(days=1)
    if rows:
        db.execute(insert(CitizenReport), rows)
    set_meta(db, "reports_until", today.isoformat())
    db.commit()
    return len(rows)


def backfill_cases(db: Session) -> int:
    """Casos semanales simulados hasta la última semana epidemiológica completa.

    No sobrescribe semanas que ya existen (por ejemplo, cargadas de la DGE)."""
    lw = last_complete_week()
    areas = db.scalars(select(Area.id)).all()
    existing = {
        (a, y, w) for a, y, w in db.execute(select(CasesWeekly.area_id, CasesWeekly.year, CasesWeekly.week)).all()
    }
    rows = []
    y, w = SEASON_START
    while (y, w) <= lw:
        t = season_t(week_start(y, w))
        for area_id in areas:
            if (area_id, y, w) in existing:
                continue
            prob, conf = simdata.weekly_cases(area_id, y, w, t)
            rows.append(dict(area_id=area_id, year=y, week=w, probable=prob, confirmed=conf, source="simulado"))
        y, w = shift_week(y, w, 1)
    if rows:
        db.execute(insert(CasesWeekly), rows)
        db.commit()
    return len(rows)


def retention_cleanup(db: Session) -> int:
    """Conserva 7 días de lecturas de microclima (cada 15 min) para no crecer sin límite."""
    cutoff = utcnow() - timedelta(days=7)
    res = db.execute(
        Reading.__table__.delete().where(Reading.kind == "clima", Reading.ts < cutoff)
    )
    db.commit()
    return res.rowcount or 0
