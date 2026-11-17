# Sentinela Aedes · Prototipo Alfa

Alerta temprana de dengue para Yucatán. Prototipo funcional con:

- **Backend en la nube** (Python · FastAPI · PostgreSQL) que ingesta, valida y persiste telemetría de ovitrampas IoT, cruza clima real y casos, calcula el riesgo de brote por colonia y municipio, pronostica casos y **envía documentos a un ERP simulado**.
- **Dashboard web responsivo** (React · Vite) que se actualiza solo cada 10 s desde el backend (4 s en la vista de operación) y funciona en el celular.

```
Nodos IoT / gateway ──HTTPS + X-Device-Key──▶ POST /api/telemetry ──▶ validación ──▶ PostgreSQL
(simulador interno y                                    │                    │ cuarentena
 scripts/node_simulator.py)                             ▼                    ▼
Open-Meteo (clima real) ─────────────▶ analítica: IPO, huevecillos/trampa, riesgo 1-2-4 semanas, pronóstico
                                                        │
Dashboard (Vercel) ◀── GET /api/dashboard, /api/ops ────┤
   │  asignar brigada / reporte / KPIs / mantenimiento  ▼
   └────────────── POST ──────────────▶ conector ERP simulado (print + bitácora + acuse)
```

## Qué datos son reales y cuáles simulados

| Dato | Fuente | Estado |
|---|---|---|
| Lluvia diaria y temperatura mín./máx. por municipio y colonia (92 días + pronóstico de 16) | API pública **Open-Meteo** | **Real**, se actualiza cada 6 h |
| Municipios, claves INEGI, coordenadas | INEGI | Real |
| Casos probables/confirmados por semana | Simulados y calibrados con las cifras oficiales 2026 citadas en el reporte (~1,500 probables a la semana 39) | Simulado · se puede reemplazar con los **datos abiertos de la DGE** (ver abajo) |
| Red de 400 ovitrampas IoT (conteos diarios de huevecillos, microclima, batería) | Simulador de flota | Simulado (los nodos aún no existen) |
| Reportes ciudadanos, auditoría de sesgos | Simulador | Simulado |

### Casos reales de la DGE (opcional)

`app/etl_dge.py` descarga el ZIP de datos abiertos de dengue de la Secretaría de Salud, filtra Yucatán, agrega por municipio y semana epidemiológica y reemplaza los casos simulados:

```bash
python -m app.etl_dge --url                # desde backend/, descarga el ZIP oficial (~1 MB)
```

En Render basta con poner `DGE_ETL_ENABLED=true` para que se cargue al arrancar.

## Integración ERP simulada

No existe un ERP: `app/erp.py → enviar_a_erp()` arma el documento como lo recibiría un ERP (folio, sociedad, centro de costos, partidas de materiales con importes), lo **imprime en la consola del servidor** (`[ERP-SIM] >>> Enviando …` visible en los logs de Render), guarda la transacción en la tabla `erp_transactions` con un acuse simulado, y el dashboard muestra una **alerta** con el folio.

| Acción en el dashboard | Documento | Endpoint |
|---|---|---|
| Asignar brigada (colonia o municipio) | `ORDEN_SERVICIO` (requisición de larvicida, adulticida y horas-hombre según el nivel de riesgo) | `POST /api/brigadas` |
| Reporte ciudadano de criadero | `AVISO_CIUDADANO` | `POST /api/reportes` |
| Nodos sin datos > 48 h | `ORDEN_MANTENIMIENTO` | `POST /api/erp/mantenimiento` |
| Sincronizar indicadores | `REPORTE_KPI` | `POST /api/erp/sync-kpis` |

La bitácora se consulta en `GET /api/erp/transacciones` y en la pestaña **Operación e integración** (clic en un folio muestra el documento completo y su acuse).

## Seguridad (insumo para la parte SOC)

- La ingesta exige la llave del dispositivo en `X-Device-Key` (en Render se genera sola).
- Lecturas imposibles o anómalas van a **cuarentena** (`quarantined_readings`).
- **Regla SIEM SA-001**: 5 o más intentos con llave inválida desde la misma IP en 60 s → evento de severidad **alta** en `security_events` (`GET /api/security/events`). Se demuestra con `python scripts/node_simulator.py --url <API> --ataque`.

## Correr en local

Requisitos: Python 3.12 o superior (probado con 3.13) y Node 18 o superior.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000   # http://127.0.0.1:8000/docs
```

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173 (usa http://localhost:8000 por defecto)
```

Sin `DATABASE_URL` el backend usa SQLite (`backend/sentinela.db`); la primera vez siembra la base (catálogo, 400 nodos, 6 semanas de lecturas) en unos segundos.

Pruebas automáticas (11 pruebas de extremo a extremo):

```bash
cd backend
python -m pytest -q
```

Simulador externo de gateway (lado Edge, envía por HTTPS):

```bash
python scripts/node_simulator.py --url http://127.0.0.1:8000 --key dev-device-key
```

## Despliegue

### 1. Backend + base de datos en Render (PaaS)

1. Subir esta carpeta a un repositorio de GitHub.
2. En Render: **New → Blueprint** → elegir el repositorio. `render.yaml` crea el servicio web `sentinela-aedes-api` y la base PostgreSQL `sentinela-aedes-db` (plan gratuito).
3. Esperar a que `https://<servicio>.onrender.com/api/health` responda `{"status":"ok"}`.
4. Copiar el valor de `DEVICE_API_KEY` (Environment del servicio) para el simulador externo.

Notas del plan gratuito: el servicio se duerme tras 15 min sin tráfico (la primera carga tarda ~1 min; abrir el dashboard un par de minutos antes de exponer) y la base PostgreSQL gratuita de Render caduca a los 30 días. Para una base permanente se puede usar Neon o Supabase y pegar su cadena en `DATABASE_URL`.

### 2. Dashboard en Vercel

1. Vercel → **Add New → Project** → mismo repositorio.
2. **Root Directory:** `frontend` (Vercel detecta Vite: build `npm run build`, salida `dist`).
3. Variable de entorno: `VITE_API_URL = https://<servicio>.onrender.com`.
4. Deploy. Después, en Render cambiar `CORS_ORIGINS` a la URL de Vercel.

### Antes de la exposición

Para borrar las brigadas, documentos ERP y eventos generados en pruebas:

```bash
curl -X POST https://<servicio>.onrender.com/api/admin/reset-demo -H "X-Device-Key: <DEVICE_API_KEY>"
```

## Endpoints principales

Documentación interactiva en `/docs` (Swagger).

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/health` | Estado del servicio |
| GET | `/api/dashboard` | Todo el tablero en una llamada (KPIs, colonias, municipios, pronóstico) |
| GET | `/api/kpis`, `/api/colonias`, `/api/municipios`, `/api/forecast` | Recursos individuales |
| POST | `/api/telemetry` | Ingesta de lecturas (una o lote de gateway) · requiere `X-Device-Key` |
| GET | `/api/telemetry/recent`, `/api/nodes` | Telemetría reciente y estado de nodos |
| POST | `/api/brigadas`, `/api/reportes` | Acciones que generan documentos ERP |
| POST | `/api/erp/sync-kpis`, `/api/erp/mantenimiento` | Documentos ERP |
| GET | `/api/erp/transacciones[/{folio}]` | Bitácora del ERP simulado |
| GET | `/api/ops`, `/api/security/events` | Operación y seguridad |

## Estructura

```
backend/
  app/
    main.py        arranque, CORS, inicialización en segundo plano
    api.py         endpoints REST
    models.py      tablas (SQLAlchemy)
    analytics.py   IPO, riesgo por colonia/municipio, pronóstico, KPIs
    telemetry.py   ingesta, validación, cuarentena, regla SIEM
    erp.py         conector ERP simulado
    weather.py     clima real (Open-Meteo)
    simulator.py   flota IoT simulada (telemetría continua)
    seed.py        siembra y backfill de series
    simdata.py     generadores deterministas de la simulación
    etl_dge.py     carga opcional de casos reales de la DGE
  scripts/node_simulator.py   gateway externo de prueba
  tests/test_api.py           pruebas de extremo a extremo
frontend/
  src/App.jsx                 pestañas, sondeo en tiempo real, alertas ERP
  src/views/                  Secretaría de Salud · Yucatán · Ciudadana · Operación
render.yaml                   blueprint de Render
```
