# Guion de exposición · 6 min de demo en vivo + 2 min de preguntas

**A** = integrante 1 · **B** = integrante 2. Proyectar el dashboard en una laptop. Tener el celular a la mano con el dashboard abierto.

## Antes de entrar al salón (10 min antes)

1. Abrir `https://<api>.onrender.com/api/health` y esperar `"status":"ok"`. El plan gratuito de Render se duerme y tarda ~1 min en despertar.
2. Limpiar los datos de prueba:
   ```bash
   curl -X POST https://<api>.onrender.com/api/admin/reset-demo -H "X-Device-Key: <DEVICE_API_KEY>"
   ```
3. Dejar abiertas estas pestañas: dashboard (Vercel), **Logs** del servicio en Render, `/docs` (Swagger) y `docs/seguridad/idmz_zero_trust.png`.
4. Tener lista una terminal con el comando del ataque (paso 4:00).
5. Respaldo: correr backend y frontend en local (`uvicorn` + `npm run dev`) por si falla la red del salón.

## Minuto a minuto

| Tiempo | Quién | Qué se muestra | Qué se dice |
|---|---|---|---|
| 0:00–0:40 | A | Dashboard, vista Secretaría de Salud | El problema: hoy se fumiga cuando ya hay casos. Sentinela anticipa el brote 1, 2 y 4 semanas por colonia con ovitrampas IoT, clima real y casos. Señalar «En vivo · actualizado hace N s». |
| 0:40–1:40 | A | Pestaña **Operación e integración** | La telemetría entra cada 5 s por `POST /api/telemetry` con llave de dispositivo. Las lecturas imposibles van a cuarentena. Todo se guarda en PostgreSQL en la nube (Render). |
| 1:40–2:40 | A | Vista Secretaría de Salud → colonia en **brote** → **Asignar brigada** | Aparece la alerta con el folio. Cambiar a la pestaña de **Logs de Render** y mostrar `[ERP-SIM] >>> Enviando ORDEN_SERVICIO …` y el acuse. No hay ERP real: se emula el documento (sociedad, centro de costos, partidas de larvicida y horas-hombre según el riesgo) y su acuse. Clic en el folio para ver el documento completo. |
| 2:40–3:30 | B | **Celular** | El mismo tablero en el teléfono, actualizándose solo. Desde el celular, en la pestaña de operación: **Orden de mantenimiento de nodos** → alerta con folio OM. El jefe de jurisdicción decide en campo, sin volver a la oficina. |
| 3:30–4:00 | B | Diagrama IDMZ | Zonas Purdue y deny-all por defecto. OT nunca habla directo con IT: todo pasa por la IDMZ. Microsegmento por sitio. Puertos explícitos (443 mTLS al ERP, 8883 desde OT y siempre iniciado desde OT). |
| 4:00–4:50 | B | Terminal → `python backend/scripts/node_simulator.py --url https://<api>.onrender.com --ataque` y luego la pestaña de operación | Regla SIEM SA-001: 5 o más llaves inválidas desde una IP en 60 s generan un evento de severidad **alta**. Mostrar el evento en el tablero. Mencionar la fuente de logs, el umbral y la acción (bloqueo en WAF / rotar llave). Está en formato Sigma. |
| 4:50–5:30 | A | Reporte, sección 2.3 | ¿Por qué PaaS? Somos 2 personas: el proveedor administra SO, TLS, respaldos y despliegue desde Git (`render.yaml`). Límites: el plan gratuito se duerme; en producción se usaría una región en México por ser datos de salud. Arquitectura híbrida: el edge y el Network Server quedan en sitio. |
| 5:30–6:00 | A | Reporte, sección 5 | Barreras: SINAVE por lotes (ETL de la DGE), ERP sin API (conector desacoplado), cultura reactiva y desconfianza en el modelo (por eso es explicable). Valor: tiempo de alerta a orden en minutos y costo por intervención trazable. Cierre. |

## Preguntas probables (las deben poder contestar **los dos**)

**¿Por qué PaaS y no IaaS?**
Con IaaS tendríamos que parchar el SO, configurar Nginx, TLS, firewall y respaldos. El PaaS nos da eso gestionado y despliegue continuo desde GitHub. El código es estándar (uvicorn + PostgreSQL), así que se puede mover a IaaS o a contenedores sin reescribirlo.

**¿Cómo se conectaría a un ERP real?**
Solo cambia el adaptador `erp.enviar_a_erp()`: en lugar de `print`, haría la llamada REST/SOAP del ERP a través del gateway de la IDMZ con mTLS. El documento canónico, el folio y la bitácora (`erp_transactions`) se quedan igual.

**¿Qué impide que alguien envíe datos falsos?**
Cuatro cosas: la llave de dispositivo en cada petición, la validación de rangos y de marca de tiempo, la comparación contra el histórico del nodo (cuarentena) y la regla SA-001 contra la fuerza bruta. En producción cada gateway tendría su propio certificado (mTLS) y se podría revocar.

**¿Por qué «tiempo real» si es sondeo cada 10 s?**
Para un pronóstico semanal, 4–10 s de latencia es más que suficiente. El sondeo atraviesa cualquier proxy y es simple de operar. Si se necesitara push, se cambiaría a WebSocket o SSE sin tocar el backend de datos.

**¿Qué pasa si se cae Internet en un municipio?**
El servidor edge guarda las lecturas (store-and-forward, búfer de 72 h) y las reenvía al volver la conexión. Las lecturas con más de 7 días de atraso se mandan a cuarentena. Los nodos sin datos por más de 48 h generan una orden de mantenimiento.

**¿Qué datos son reales?**
El clima es real (Open-Meteo, se actualiza cada 6 h). Los casos están simulados y calibrados con cifras oficiales; `etl_dge.py` puede cargar los casos reales de la DGE. La telemetría es simulada porque los nodos aún no existen, pero entra por la misma API y las mismas validaciones.

**¿Qué falso positivo tiene la regla SIEM?**
Un gateway propio que se quedó con la llave anterior después de rotarla. Se distingue con el inventario de IPs de gateways, y la regla emite como máximo una alerta por IP por minuto para no saturar al SOC.

**¿Qué es la IDMZ y por qué no conectar directo?**
Es una zona intermedia (nivel 3.5) donde terminan todas las conexiones entre IT, OT y la nube. Si comprometen IT, no hay ruta directa a los sensores, y viceversa.
