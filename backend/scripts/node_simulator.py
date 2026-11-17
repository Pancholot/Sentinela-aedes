"""Simulador EXTERNO de un gateway LoRaWAN/NB-IoT que envía telemetría a la API.

Representa el lado "Edge" de la arquitectura: los nodos cuentan huevecillos
en el dispositivo y el gateway envía solo números a la nube por HTTPS, con
la llave del dispositivo en el encabezado X-Device-Key. Solo usa la
biblioteca estándar de Python.

Ejemplos:
  python scripts/node_simulator.py --url http://localhost:8000 --key dev-device-key
  python scripts/node_simulator.py --url https://<tu-api>.onrender.com --key <DEVICE_API_KEY> --interval 2
  python scripts/node_simulator.py --url ... --key ... --anomalia     # manda lecturas imposibles (cuarentena)
  python scripts/node_simulator.py --url ... --ataque                  # llaves inválidas (dispara la regla SIEM)
"""
import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def call(method: str, url: str, body: dict | None = None, key: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-Device-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"{}")
        except json.JSONDecodeError:
            return err.code, {}


def wait_ready(base: str) -> None:
    for _ in range(60):
        try:
            code, body = call("GET", f"{base}/api/health")
            if code == 200 and body.get("ready"):
                return
        except (urllib.error.URLError, TimeoutError):
            pass
        print("Esperando a que la API despierte…")
        time.sleep(3)
    sys.exit("La API no respondió")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--key", default="dev-device-key")
    ap.add_argument("--gateway", default="GW-MERIDA-01")
    ap.add_argument("--interval", type=float, default=3.0, help="segundos entre lotes")
    ap.add_argument("--batch", type=int, default=5, help="lecturas por lote")
    ap.add_argument("--count", type=int, default=0, help="número de lotes (0 = infinito)")
    ap.add_argument("--anomalia", action="store_true", help="incluir lecturas imposibles")
    ap.add_argument("--ataque", action="store_true", help="enviar llaves inválidas (prueba SIEM)")
    args = ap.parse_args()
    base = args.url.rstrip("/")
    wait_ready(base)

    if args.ataque:
        for i in range(8):
            code, body = call("POST", f"{base}/api/telemetry", {"node_id": "OVI-0001", "kind": "clima", "temp_c": 27},
                              key=f"llave-falsa-{i}")
            print(f"intento {i + 1}: HTTP {code} {body.get('detail', '')}")
        code, events = call("GET", f"{base}/api/security/events?limit=3")
        print("Eventos de seguridad:", json.dumps(events, ensure_ascii=False, indent=2))
        return

    code, nodes = call("GET", f"{base}/api/nodes?status=online")
    ids = [n["id"] for n in nodes] if code == 200 else []
    if not ids:
        sys.exit("No se pudo obtener la lista de nodos")
    print(f"Gateway {args.gateway}: {len(ids)} nodos en línea. Enviando a {base}/api/telemetry (Ctrl+C para salir)")
    sent = 0
    while args.count == 0 or sent < args.count:
        readings = []
        for node in random.sample(ids, k=min(args.batch, len(ids))):
            readings.append({
                "node_id": node, "kind": "clima", "ts": datetime.now(timezone.utc).isoformat(),
                "temp_c": round(random.uniform(24, 32), 1), "humidity": round(random.uniform(60, 95), 1),
                "battery_v": round(random.uniform(3.7, 4.1), 2), "rssi": random.randint(-118, -70),
            })
        if args.anomalia:
            readings.append({"node_id": random.choice(ids), "kind": "clima", "temp_c": 88.0, "humidity": 10})
        code, body = call("POST", f"{base}/api/telemetry", {"gateway_id": args.gateway, "readings": readings}, key=args.key)
        stamp = datetime.now().strftime("%H:%M:%S")
        if code == 200:
            print(f"[{stamp}] lote {sent + 1}: {body['accepted']} aceptadas, {body['quarantined']} en cuarentena")
        else:
            print(f"[{stamp}] HTTP {code}: {body}")
        sent += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
