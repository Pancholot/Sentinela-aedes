"""Pruebas de extremo a extremo de la API (base SQLite temporal, sin red).

Ejecutar desde backend/:  python -m pytest -q
"""
import os
import tempfile
import time

_tmp = tempfile.mkdtemp()
# TEST_DATABASE_URL permite correr las mismas pruebas contra PostgreSQL (base vacía).
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{os.path.join(_tmp, 'test.db')}".replace("\\", "/")
os.environ["SIMULATOR_ENABLED"] = "false"
os.environ["WEATHER_ENABLED"] = "false"
os.environ["DEVICE_API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

KEY = {"X-Device-Key": "test-key"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        for _ in range(240):
            if c.get("/api/health").json()["ready"]:
                break
            time.sleep(0.25)
        else:
            pytest.fail("El backend no terminó de inicializar")
        yield c


def test_health_and_root(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/").json()["servicio"] == "Sentinela Aedes API"


def test_dashboard_shape(client):
    d = client.get("/api/dashboard").json()
    assert len(d["colonias"]) == 20 and len(d["municipios"]) == 21
    k = d["kpis"]
    assert k["nodes_total"] == 400 and k["nodes_online"] == 382
    assert k["rural_total"] == 100 and k["rural_online"] == 94
    for c in d["colonias"]:
        assert len(c["p"]) == 3 and all(0 <= p <= 100 for p in c["p"])
        assert c["p"][0] <= c["p"][1] <= c["p"][2]
        assert len(c["trend"]) == 4 and len(c["drivers"]) == 3
    f = d["forecast"]
    assert len(f["observed"]) == 11 and len(f["mean"]) == 4 and len(f["weeks"]) == 15
    assert all(lo <= m <= hi for lo, m, hi in zip(f["lo"], f["mean"], f["hi"]))
    assert d["meta"]["weather_source"] == "simulado"  # WEATHER_ENABLED=false


def test_telemetry_requires_key(client):
    r = client.post("/api/telemetry", json={"node_id": "OVI-0001", "kind": "clima", "temp_c": 27.0})
    assert r.status_code == 401


def test_telemetry_accepts_and_quarantines(client):
    good = {"node_id": "OVI-0147", "kind": "clima", "temp_c": 27.5, "humidity": 80, "battery_v": 3.9, "rssi": -95}
    r = client.post("/api/telemetry", json=good, headers=KEY).json()
    assert r["accepted"] == 1
    batch = {"gateway_id": "GW-PETO-01", "readings": [
        {"node_id": "OVI-0147", "kind": "clima", "temp_c": 78.0},  # imposible
        {"node_id": "OVI-9999", "kind": "clima", "temp_c": 27.0},  # nodo desconocido
        {"node_id": "OVI-0002", "kind": "huevos", "eggs_count": 9999},  # conteo imposible
        {"node_id": "OVI-0003", "kind": "clima", "temp_c": 26.1, "humidity": 85},
    ]}
    r = client.post("/api/telemetry", json=batch, headers=KEY).json()
    assert r["received"] == 4 and r["accepted"] == 1 and r["quarantined"] == 3
    recent = client.get("/api/telemetry/recent?limit=5").json()
    assert recent[0]["node_id"] == "OVI-0003"
    ops = client.get("/api/ops").json()
    assert ops["ingest"]["quarantined_24h"] >= 3
    assert len(ops["offline_nodes"]) == 18


def test_brute_force_rule(client):
    for _ in range(6):
        client.post("/api/telemetry", json={"node_id": "OVI-0001"}, headers={"X-Device-Key": "mala"})
    kinds = [e["kind"] for e in client.get("/api/security/events").json()]
    assert "brute_force" in kinds


def test_siem_ignores_spoofed_forwarded_for(client):
    # El atacante cambia la IP falsa en cada intento; el borde agrega la IP real y luego
    # los proxies internos agregan IPs privadas (forma real observada en Render).
    for i in range(6):
        client.post("/api/telemetry", json={"node_id": "OVI-0001"},
                    headers={"X-Device-Key": "mala", "X-Forwarded-For": f"1.2.3.{i}, 8.8.4.4, 10.29.49.105"})
    events = client.get("/api/security/events?limit=20").json()
    fails = {e["source_ip"] for e in events if e["kind"] == "auth_fail"}
    assert "8.8.4.4" in fails and not any(ip.startswith("1.2.3.") or ip.startswith("10.") for ip in fails)
    assert any(e["kind"] == "brute_force" and e["source_ip"] == "8.8.4.4" for e in events)
    # Detrás de Cloudflare manda CF-Connecting-IP (lo escribe Cloudflare, no el cliente).
    client.post("/api/telemetry", json={"node_id": "OVI-0001"},
                headers={"X-Device-Key": "mala", "CF-Connecting-IP": "9.9.9.9",
                         "X-Forwarded-For": "1.2.3.4, 9.9.9.9, 172.64.203.116, 10.29.49.105"})
    assert client.get("/api/security/events?limit=1").json()[0]["source_ip"] == "9.9.9.9"


def test_brigada_sends_erp_order(client):
    r = client.post("/api/brigadas", json={"area_id": "col:mulsay", "horizon": 1}).json()
    assert r["created"] is True
    erp = r["erp"]
    assert erp["doc_type"] == "ORDEN_SERVICIO" and erp["status"] == "CONFIRMADO"
    assert erp["folio"].startswith("OS-")
    assert erp["document"]["datos"]["partidas"], "la orden debe llevar requisición de materiales"
    again = client.post("/api/brigadas", json={"area_id": "col:mulsay", "horizon": 1}).json()
    assert again["created"] is False
    col = client.get("/api/colonias/mulsay").json()
    assert col["assigned"] is True and col["assignment"]["folio"] == erp["folio"]
    r = client.post("/api/brigadas", json={"area_id": "mun:sotuta", "horizon": 2}).json()
    assert r["created"] is True


def test_reporte_ciudadano(client):
    before = client.get("/api/kpis").json()["kpis"]["reports_validated"]
    r = client.post("/api/reportes", json={"colonia": "castilla", "descripcion": "Llantas con agua", "con_foto": True}).json()
    assert r["folio"].startswith("SA-") and r["erp"]["doc_type"] == "AVISO_CIUDADANO"
    after = client.get("/api/kpis").json()["kpis"]["reports_validated"]
    assert after == before + 1
    assert client.post("/api/reportes", json={"colonia": "no-existe"}).status_code == 404


def test_erp_maintenance_and_kpis(client):
    r = client.post("/api/erp/mantenimiento").json()
    assert r["created"] is True and r["nodes"] == 18
    assert client.post("/api/erp/mantenimiento").json()["created"] is False
    r = client.post("/api/erp/sync-kpis").json()
    assert r["erp"]["doc_type"] == "REPORTE_KPI"
    tx = client.get("/api/erp/transacciones?limit=50").json()
    assert {t["doc_type"] for t in tx} >= {"ORDEN_SERVICIO", "AVISO_CIUDADANO", "ORDEN_MANTENIMIENTO", "REPORTE_KPI"}
    one = client.get(f"/api/erp/transacciones/{tx[0]['folio']}").json()
    assert one["document"]["sistema_origen"] == "SENTINELA-AEDES"


def test_reset_demo(client):
    assert client.post("/api/admin/reset-demo").status_code == 401
    r = client.post("/api/admin/reset-demo", headers=KEY).json()
    assert r["reset"] is True and r["eliminados"]["documentos_erp"] >= 4
    assert client.get("/api/erp/transacciones").json() == []
    assert client.get("/api/colonias/mulsay").json()["assigned"] is False
    # Después del reinicio los folios siguen siendo únicos.
    r = client.post("/api/brigadas", json={"area_id": "col:mulsay", "horizon": 0}).json()
    assert r["created"] is True


def test_simulator_tick_ingests(client):
    from app.simulator import FleetSimulator
    before = client.get("/api/ops").json()["ingest"]["readings_last_min"]
    sim = FleetSimulator(5)
    for _ in range(3):
        sim.tick()
    after = client.get("/api/ops").json()["ingest"]["readings_last_min"]
    assert after >= before + 6


def test_epi_week():
    from datetime import date
    from app.timeutil import epi_week
    assert epi_week(date(2026, 1, 4)) == (2026, 1)
    assert epi_week(date(2026, 1, 3)) == (2025, 53)
    assert epi_week(date(2026, 11, 11)) == (2026, 45)
    assert epi_week(date(2026, 12, 31)) == (2026, 52)
