"""ETL opcional: casos REALES de dengue desde los datos abiertos de la DGE.

Fuente: Secretaría de Salud, Dirección General de Epidemiología, "Datos
abiertos de enfermedades transmitidas por vector (dengue)". Archivo ZIP con
un CSV de casos (un renglón por caso, sin datos personales).

El ETL filtra Yucatán (ENTIDAD_RES = 31), descarta los casos con
ESTATUS_CASO = 3 (descartado), asigna la semana epidemiológica según la fecha
de inicio de síntomas y agrega casos probables (estatus 1 y 2) y confirmados
(estatus 2) por municipio y semana. Los registros reemplazan a los simulados
en la tabla cases_weekly (fuente = "DGE").

Uso:
    python -m app.etl_dge --file ruta/datos_abiertos_dengue.zip
    python -m app.etl_dge --url   (descarga del portal de la DGE)
"""
import argparse
import csv
import io
import logging
import zipfile
from collections import defaultdict
from datetime import date

import httpx
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from .config import settings
from .models import Area, CasesWeekly
from .seed import set_meta
from .timeutil import epi_week, last_complete_week, shift_week

log = logging.getLogger("sentinela.etl_dge")

YUCATAN = 31


def _open_csv(raw: bytes) -> io.TextIOBase:
    if raw[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(raw))
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        raw = zf.read(name)
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return io.StringIO(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo decodificar el CSV de la DGE")


def _int(v) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _date(v) -> date | None:
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def aggregate(text: io.TextIOBase) -> tuple[dict, dict]:
    reader = csv.DictReader(text)
    cols = {c.upper().strip(): c for c in (reader.fieldnames or [])}
    need = ["ENTIDAD_RES", "MUNICIPIO_RES", "FECHA_SIGN_SINTOMAS", "ESTATUS_CASO"]
    missing = [c for c in need if c not in cols]
    if missing:
        raise ValueError(f"El CSV no tiene las columnas esperadas: {missing}")
    by_mun: dict[tuple[str, int, int], list[int]] = defaultdict(lambda: [0, 0])
    by_state: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    for row in reader:
        if _int(row[cols["ENTIDAD_RES"]]) != YUCATAN:
            continue
        status = _int(row[cols["ESTATUS_CASO"]])
        if status not in (1, 2):
            continue
        d = _date(row[cols["FECHA_SIGN_SINTOMAS"]])
        if d is None:
            continue
        y, w = epi_week(d)
        mun = _int(row[cols["MUNICIPIO_RES"]])
        code = f"{mun:03d}" if mun is not None else "999"
        for acc in (by_mun[(code, y, w)], by_state[(y, w)]):
            acc[0] += 1
            acc[1] += 1 if status == 2 else 0
    return by_mun, by_state


def load(db: Session, raw: bytes) -> dict:
    by_mun, by_state = aggregate(_open_csv(raw))
    if not by_state:
        raise ValueError("El archivo no contiene casos de Yucatán")
    muns = {a.inegi_code: a.id for a in db.scalars(select(Area).where(Area.kind == "municipio")).all()}
    first = min(by_state)
    lw = last_complete_week()
    weeks = []
    y, w = first
    while (y, w) <= lw:
        weeks.append((y, w))
        y, w = shift_week(y, w, 1)
    rows = []
    for (y, w) in weeks:
        p, c = by_state.get((y, w), (0, 0))
        rows.append(dict(area_id="edo:yucatan", year=y, week=w, probable=p, confirmed=c, source="DGE"))
        for code, area_id in muns.items():
            p, c = by_mun.get((code, y, w), (0, 0))
            rows.append(dict(area_id=area_id, year=y, week=w, probable=p, confirmed=c, source="DGE"))
    area_ids = ["edo:yucatan", *muns.values()]
    for (y, w) in weeks:
        db.execute(delete(CasesWeekly).where(CasesWeekly.area_id.in_(area_ids), CasesWeekly.year == y,
                                             CasesWeekly.week == w))
    db.execute(insert(CasesWeekly), rows)
    set_meta(db, "cases_source", "DGE")
    db.commit()
    total = sum(v[0] for v in by_state.values())
    log.info("DGE: %s casos de Yucatán cargados (%s semanas)", total, len(weeks))
    return {"casos_yucatan": total, "semanas": len(weeks), "desde": f"{first[0]}-S{first[1]}"}


def download() -> bytes:
    resp = httpx.get(settings.dge_url, timeout=120.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def main() -> None:
    from .db import Base, SessionLocal, engine
    from . import models  # noqa: F401
    from .seed import seed_if_empty

    parser = argparse.ArgumentParser(description="Carga casos reales de dengue (DGE) en la base")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="Ruta al ZIP o CSV descargado")
    src.add_argument("--url", action="store_true", help="Descargar del portal de datos abiertos")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(engine)
    raw = open(args.file, "rb").read() if args.file else download()
    with SessionLocal() as db:
        seed_if_empty(db)
        print(load(db, raw))


if __name__ == "__main__":
    main()
