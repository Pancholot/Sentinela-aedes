import { useCallback, useEffect, useRef, useState } from 'react';
import { API_URL, api } from './api.js';
import Toasts from './components/Toasts.jsx';
import { C, H_LABELS, LEVELS, lv, timeAgo } from './theme.js';
import CitView from './views/CitView.jsx';
import EdoView from './views/EdoView.jsx';
import OpsView from './views/OpsView.jsx';
import SSYView from './views/SSYView.jsx';

const DASH_MS = 10000; // KPIs y mapas: cada 10 s
const OPS_MS = 4000; // telemetría en vivo: cada 4 s

function usePolling(path, ms, enabled = true) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [at, setAt] = useState(null);
  const busy = useRef(false);
  const load = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    try {
      setData(await api.get(path));
      setError(null);
      setAt(Date.now());
    } catch (e) {
      setError(e);
    } finally {
      busy.current = false;
    }
  }, [path]);
  useEffect(() => {
    if (!enabled) return undefined;
    load();
    const id = setInterval(load, ms);
    return () => clearInterval(id);
  }, [load, ms, enabled]);
  return { data, error, at, reload: load };
}

function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

const TABS = [
  ['ssy', 'Secretaría de Salud'],
  ['edo', 'Yucatán por municipio'],
  ['cit', 'Vista ciudadana'],
  ['ops', 'Operación e integración'],
];

export default function App() {
  const [view, setView] = useState('ssy');
  const [h, setH] = useState(1);
  const [layers, setLayers] = useState({ ovi: true, crd: false, rain: false });
  const [sel, setSel] = useState('castilla');
  const [mun, setMun] = useState('sotuta');
  const [cit, setCit] = useState('mulsay');
  const [busy, setBusy] = useState(null);
  const [toasts, setToasts] = useState([]);
  const now = useNow();

  const dash = usePolling('/api/dashboard', DASH_MS);
  const ops = usePolling('/api/ops', OPS_MS, view === 'ops');
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [view]);

  const closeToast = (id) => setToasts((ts) => ts.filter((t) => t.id !== id));
  const toast = (t) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((ts) => [...ts.slice(-3), { id, ...t }]);
    return id;
  };
  const updateToast = (id, patch, ttl = 9000) => {
    setToasts((ts) => ts.map((t) => (t.id === id ? { ...t, ...patch } : t)));
    if (ttl) setTimeout(() => closeToast(id), ttl);
  };

  // Envía un documento al ERP (simulado) y muestra la alerta con el folio y el acuse.
  const sendToErp = async (key, what, call) => {
    setBusy(key);
    const id = toast({ kind: 'pending', title: 'Enviando información al ERP…', body: what });
    console.info(`[ERP] Enviando al ERP de la SSY: ${what}`);
    try {
      const r = await call();
      if (r.erp) {
        console.info(`[ERP] Acuse ${r.erp.ack?.estado} · folio ${r.erp.folio} · documento ERP ${r.erp.ack?.id_documento_erp}`, r.erp);
        updateToast(id, {
          kind: 'ok',
          title: `${r.created === false ? 'Ya estaba en el ERP' : 'ERP recibió'} ${r.erp.folio}`,
          body: `${r.erp.summary} · documento ERP ${r.erp.ack?.id_documento_erp || '—'}`,
        });
      } else {
        updateToast(id, { kind: 'ok', title: r.message || 'Sin cambios', body: '' });
      }
      dash.reload();
      if (view === 'ops') ops.reload();
      return r;
    } catch (e) {
      updateToast(id, { kind: 'error', title: 'No se pudo enviar al ERP', body: e.message });
      return null;
    } finally {
      setBusy(null);
    }
  };

  const assign = (item) => {
    const l = lv(item.p[h]);
    return sendToErp(item.key, `Orden de servicio: brigada a ${item.name} (riesgo ${LEVELS[l]}, ${item.p[h]}% a ${H_LABELS[h]})`, () =>
      api.post('/api/brigadas', { area_id: item.key, horizon: h })
    );
  };
  const report = (body) => {
    const name = d?.colonias.find((c) => c.id === body.colonia)?.name || body.colonia;
    return sendToErp('report', `Aviso de criadero en ${name}`, () => api.post('/api/reportes', body));
  };
  const erpAction = (kind) =>
    kind === 'sync'
      ? sendToErp('sync', 'Reporte semanal de KPIs', () => api.post('/api/erp/sync-kpis'))
      : sendToErp('mant', 'Orden de mantenimiento de nodos sin datos', () => api.post('/api/erp/mantenimiento'));

  const d = dash.data;
  const online = d && !dash.error;
  const weatherReal = d?.meta.weather_source === 'open-meteo';

  return (
    <div className="page" style={{ minHeight: '100vh', padding: '24px 24px 48px' }}>
      <div style={{ maxWidth: 1320, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
        <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true">
              <rect width="40" height="40" rx="10" fill={C.teal} />
              <path d="M12 26c4-10 12-10 16 0M20 12v6M14 15l3 4M26 15l-3 4" stroke="#FFFFFF" strokeWidth="2.2" fill="none" strokeLinecap="round" />
            </svg>
            <div>
              <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-0.01em' }}>Sentinela Aedes</h1>
              <p style={{ margin: '2px 0 0', fontSize: 13, color: C.muted }}>
                Vigilancia predictiva de dengue · Yucatán{d ? ` · Semana epidemiológica ${d.meta.epi_week} de ${d.meta.epi_year}` : ''}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: C.muted }} title={`Backend: ${API_URL}`}>
              <span className={`live-dot${online ? '' : ' off'}`} />
              {online ? `En vivo · actualizado ${timeAgo(new Date(dash.at).toISOString(), now)}` : d ? 'Reconectando…' : 'Conectando…'}
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#7A4A00', background: '#FCEFD2', border: '1px solid #E9C77A', borderRadius: 999, padding: '4px 10px' }}>
              Prototipo · {weatherReal ? 'clima real · ' : ''}telemetría simulada
            </span>
            <nav className="tabs" aria-label="Vistas" style={{ display: 'flex', flexWrap: 'wrap', background: '#FFFFFF', border: `1px solid ${C.line}`, borderRadius: 10, padding: 4, gap: 4 }}>
              {TABS.map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  aria-current={view === key ? 'page' : undefined}
                  onClick={() => setView(key)}
                  style={{ border: 0, borderRadius: 7, padding: '10px 14px', minHeight: 40, fontSize: 14, fontWeight: 600, cursor: 'pointer', background: view === key ? C.teal : 'transparent', color: view === key ? '#FFFFFF' : C.ink }}
                >
                  {label}
                </button>
              ))}
            </nav>
          </div>
        </header>

        {!d ? (
          <Loading error={dash.error} />
        ) : (
          <>
            {view === 'ssy' && (
              <SSYView data={d} h={h} setH={setH} layers={layers} setLayers={setLayers} sel={sel} setSel={setSel} onAssign={assign} busy={busy} now={now} />
            )}
            {view === 'edo' && <EdoView data={d} h={h} setH={setH} mun={mun} setMun={setMun} onAssign={assign} busy={busy} />}
            {view === 'cit' && <CitView data={d} cit={cit} setCit={setCit} onReport={report} />}
            {view === 'ops' && <OpsView ops={ops.data} kpis={d.kpis} onErp={erpAction} busy={busy} now={now} apiUrl={API_URL} />}
          </>
        )}
      </div>
      <Toasts items={toasts} onClose={closeToast} />
    </div>
  );
}

function Loading({ error }) {
  const starting = error?.status === 503;
  return (
    <div style={{ background: '#FFFFFF', border: `1px solid ${C.line}`, borderRadius: 12, padding: 24, display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 640 }}>
      <strong style={{ fontSize: 16 }}>{starting ? 'El backend está preparando la base de datos…' : error ? 'No hay conexión con el backend' : 'Conectando con el backend…'}</strong>
      <p style={{ margin: 0, fontSize: 13.5, color: C.muted, lineHeight: 1.5 }}>
        {error && !starting
          ? `${error.message}. Se reintenta automáticamente cada 10 s.`
          : 'El servidor gratuito de Render se duerme tras 15 minutos sin uso; la primera carga puede tardar hasta un minuto.'}
      </p>
      <p style={{ margin: 0, fontSize: 12.5, color: C.muted }}>
        API: <span className="mono">{API_URL}</span>
      </p>
    </div>
  );
}
