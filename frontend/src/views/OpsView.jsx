import { useState } from 'react';
import { api } from '../api.js';
import { Kpi, KpiRow, Panel, PanelHead, Row } from '../components/ui.jsx';
import { C, clock, fmt, mono, timeAgo } from '../theme.js';

const DOC_LABEL = {
  ORDEN_SERVICIO: 'Orden de servicio',
  AVISO_CIUDADANO: 'Aviso ciudadano',
  ORDEN_MANTENIMIENTO: 'Orden de mantenimiento',
  REPORTE_KPI: 'Reporte de KPIs',
};
const SEV = { alta: ['#9E1F1A', '#FFFFFF'], media: ['#F4D88A', '#17211F'], baja: ['#E3EEE6', '#17211F'] };

const btn = { border: `1px solid ${C.teal}`, background: '#FFFFFF', color: C.teal, borderRadius: 8, padding: '8px 12px', minHeight: 40, fontSize: 13, fontWeight: 600, cursor: 'pointer' };
const empty = (txt) => <p style={{ margin: 0, fontSize: 13, color: C.muted }}>{txt}</p>;

export default function OpsView({ ops, kpis, onErp, busy, now, apiUrl }) {
  const [doc, setDoc] = useState(null);
  if (!ops) return <p style={{ color: C.muted }}>Cargando operación…</p>;
  const ing = ops.ingest;

  const openDoc = async (folio) => {
    try {
      setDoc(await api.get(`/api/erp/transacciones/${encodeURIComponent(folio)}`));
    } catch (e) {
      setDoc({ error: e.message });
    }
  };

  return (
    <>
      <KpiRow label="Ingesta de telemetría">
        <Kpi label="Lecturas en el último minuto" value={ing.readings_last_min} sub={ing.simulator ? `flota simulada · lote cada ${ing.simulator_interval_s} s` : 'simulador apagado'} />
        <Kpi label="Lecturas en 24 h" value={fmt(ing.readings_24h)} sub="conteos diarios + microclima" />
        <Kpi label="Lecturas en cuarentena (24 h)" value={ing.quarantined_24h} sub="valores imposibles o anómalos" color={ing.quarantined_24h ? C.orange : C.ink} />
        <Kpi label="Nodos sin datos > 48 h" value={ops.offline_nodes.length} sub={`de ${kpis.nodes_total} ovitrampas IoT`} />
        <Kpi label="Eventos de seguridad (24 h)" value={ing.security_24h} sub="fuente para reglas SIEM" color={ing.security_24h ? C.orange : C.ink} />
      </KpiRow>

      <Row>
        <Panel label="Telemetría en vivo" grow>
          <PanelHead title="Telemetría en vivo" right={`POST ${apiUrl.replace(/^https?:\/\//, '')}/api/telemetry · actualizado ${clock(ops.generated_at)}`} />
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr><th>Hora</th><th>Nodo</th><th>Ubicación</th><th>Tipo</th><th>Huevecillos</th><th>Temp.</th><th>Humedad</th><th>Batería</th><th className="hide-mobile">Origen</th></tr>
              </thead>
              <tbody>
                {ops.telemetry.map((r) => (
                  <tr key={r.id} className={Date.now() - new Date(r.ts).getTime() < 12000 ? 'fresh' : undefined}>
                    <td style={mono}>{clock(r.ts)}</td>
                    <td style={mono}>{r.node_id}</td>
                    <td>{r.area}</td>
                    <td>{r.kind === 'huevos' ? 'Conteo diario' : 'Microclima'}</td>
                    <td style={mono}>{r.eggs_count != null ? `${r.eggs_count} (+${r.eggs_delta ?? 0})` : '—'}</td>
                    <td style={mono}>{r.temp_c != null ? `${r.temp_c} °C` : '—'}</td>
                    <td style={mono}>{r.humidity != null ? `${r.humidity}%` : '—'}</td>
                    <td style={mono}>{r.battery_v != null ? `${r.battery_v} V` : '—'}</td>
                    <td className="hide-mobile">{r.source === 'sim' ? 'flota simulada' : r.source === 'device' ? 'gateway / API' : 'histórico'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h3 style={{ margin: '4px 0 6px', fontSize: 13.5, fontWeight: 600 }}>Cuarentena de datos (calidad)</h3>
            {ops.quarantine.length === 0
              ? empty('Sin lecturas en cuarentena.')
              : (
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.6 }}>
                  {ops.quarantine.map((q, i) => (
                    <li key={i}><span style={mono}>{clock(q.ts)} · {q.node_id}</span> — {q.reason}</li>
                  ))}
                </ul>
              )}
          </div>
        </Panel>

        <Panel label="Integración ERP">
          <PanelHead title="Integración con ERP (simulada)" right={`${ops.erp.length} documentos recientes`} />
          <p style={{ margin: 0, fontSize: 12.5, color: C.muted, lineHeight: 1.5 }}>
            Cada acción del tablero genera un documento para el ERP de la SSY (órdenes de servicio, avisos, mantenimiento, KPIs). No hay ERP real: el backend imprime el envío en su consola y registra el acuse simulado.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <button type="button" style={btn} disabled={busy === 'sync'} onClick={() => onErp('sync')}>
              {busy === 'sync' ? 'Enviando…' : 'Sincronizar KPIs con ERP'}
            </button>
            <button type="button" style={btn} disabled={busy === 'mant'} onClick={() => onErp('mant')}>
              {busy === 'mant' ? 'Enviando…' : 'Orden de mantenimiento de nodos'}
            </button>
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {ops.erp.length === 0 && empty('Aún no se han enviado documentos. Asigna una brigada o sincroniza los KPIs.')}
            {ops.erp.map((t) => (
              <li key={t.folio}>
                <button type="button" onClick={() => openDoc(t.folio)} style={{ width: '100%', textAlign: 'left', border: `1px solid ${C.soft}`, background: '#FFFFFF', borderRadius: 10, padding: '8px 10px', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5 }}>
                    <span style={{ ...mono, fontWeight: 600, color: C.teal }}>{t.folio}</span>
                    <span style={{ color: C.green, fontWeight: 600 }}>{t.status === 'CONFIRMADO' ? '✓ Acuse recibido' : t.status}</span>
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: C.ink }}>{DOC_LABEL[t.doc_type] || t.doc_type}</span>
                  <span style={{ fontSize: 12.5, color: C.muted }}>{t.summary} · {timeAgo(t.created_at, now)}</span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      </Row>

      <Row>
        <Panel label="Nodos sin datos" grow>
          <PanelHead title="Falla técnica: nodos sin datos por más de 48 h" right="alerta al equipo técnico" />
          {ops.offline_nodes.length === 0 ? empty('Todos los nodos reportan.') : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead><tr><th>Nodo</th><th>Ubicación</th><th>Última lectura</th><th>Batería</th><th>Estado</th></tr></thead>
                <tbody>
                  {ops.offline_nodes.map((n) => (
                    <tr key={n.id}>
                      <td style={mono}>{n.id}</td>
                      <td>{n.area}</td>
                      <td>{timeAgo(n.last_seen, now)}</td>
                      <td style={mono}>{n.battery_v != null ? `${n.battery_v} V` : '—'}</td>
                      <td>{n.status === 'mantenimiento_programado' ? 'Mantenimiento programado' : 'Sin datos'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel label="Seguridad">
          <PanelHead title="Eventos de seguridad (SOC)" right="regla SA-001: ≥5 llaves inválidas en 60 s" />
          {ops.security.length === 0 ? empty('Sin eventos. Prueba: python scripts/node_simulator.py --ataque') : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {ops.security.map((e, i) => {
                const [bg, fg] = SEV[e.severity] || SEV.baja;
                return (
                  <li key={i} style={{ border: `1px solid ${C.soft}`, borderRadius: 10, padding: '8px 10px', fontSize: 12.5, display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 6, padding: '2px 6px', background: bg, color: fg }}>{e.severity.toUpperCase()}</span>
                      <span style={{ ...mono }}>{clock(e.ts)}</span>
                      <span style={{ color: C.muted }}>{e.source_ip}</span>
                    </span>
                    <span>{e.detail}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </Row>

      {doc && (
        <div role="dialog" aria-modal="true" aria-label="Documento enviado al ERP" onClick={() => setDoc(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(23,33,31,0.45)', display: 'grid', placeItems: 'center', padding: 16, zIndex: 40 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#FFFFFF', borderRadius: 14, width: 'min(720px, 100%)', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: `1px solid ${C.soft}` }}>
              <strong style={{ fontSize: 15 }}>{doc.error ? 'Error' : `Documento ${doc.folio} · ${DOC_LABEL[doc.doc_type] || doc.doc_type}`}</strong>
              <button type="button" onClick={() => setDoc(null)} aria-label="Cerrar" style={{ border: 0, background: 'none', fontSize: 22, cursor: 'pointer', color: C.muted }}>×</button>
            </div>
            <pre style={{ margin: 0, padding: 16, overflow: 'auto', fontSize: 12, lineHeight: 1.45, ...mono, background: '#F7F9F8' }}>
              {doc.error || JSON.stringify({ documento_enviado: doc.document, acuse_erp: doc.ack }, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}
