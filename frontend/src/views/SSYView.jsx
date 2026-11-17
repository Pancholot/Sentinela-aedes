import ForecastChart from '../components/ForecastChart.jsx';
import { AssignBlock, Drivers, HorizonPicker, Kpi, KpiRow, LevelTag, Panel, PanelHead, RiskLegend, Row } from '../components/ui.jsx';
import { BGS, C, FGS, H_FORECAST_IDX, H_LABELS, LEVELS, card, fmt, lv, mono, timeAgo } from '../theme.js';

const ACTIONS = [
  'Vigilancia de rutina. Mantener ovitrampas y promoción de patio limpio.',
  'Reforzar promoción en la colonia y revisar criaderos reportados en 7 días.',
  'Enviar brigada de control larvario y eliminación de criaderos esta semana; alerta preventiva a vecinos.',
  'Control larvario y nebulización focalizada en 48 horas; aviso a hospitales de la zona y alerta a vecinos.',
];

export default function SSYView({ data, h, setH, layers, setLayers, sel, setSel, onAssign, busy, now }) {
  const { colonias, forecast: f, kpis: k } = data;
  const cols = colonias.map((c) => ({ ...c, pH: c.p[h], l: lv(c.p[h]) }));
  const sc = cols.find((c) => c.id === sel) || cols[0];
  const ranked = cols.filter((c) => c.l >= 2).sort((a, b) => b.pH - a.pH);
  const nOut = cols.filter((c) => c.l === 3).length;
  const hIdx = H_FORECAST_IDX[h];
  const kv = f.mean[hIdx];
  const kWeek = f.weeks[f.observed.length + hIdx];
  const title = f.already_above
    ? 'Los casos ya están por encima del umbral epidémico'
    : f.cross_week
      ? `El pronóstico cruza el umbral epidémico en la semana ${f.cross_week}`
      : 'El pronóstico se mantiene por debajo del umbral epidémico';

  const toggle = (key) => setLayers({ ...layers, [key]: !layers[key] });

  return (
    <>
      <section aria-label="Controles" style={{ ...card, padding: '12px 16px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <HorizonPicker h={h} setH={setH} labels={H_LABELS} />
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 18, fontSize: 13 }}>
          <span style={{ fontWeight: 600, color: C.muted }}>Capas del mapa</span>
          {[
            ['ovi', 'Huevecillos por ovitrampa'],
            ['crd', 'Criaderos reportados'],
            ['rain', 'Lluvia acumulada'],
          ].map(([key, label]) => (
            <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
              <input type="checkbox" checked={layers[key]} onChange={() => toggle(key)} /> {label}
            </label>
          ))}
        </div>
      </section>

      <KpiRow label="Indicadores clave">
        <Kpi
          label="Casos probables pronosticados"
          value={kv}
          color={kv >= f.threshold ? C.red : C.ink}
          sub={`semana ${kWeek} · umbral ${f.threshold} · ${kv >= f.threshold ? 'por encima del umbral' : 'por debajo del umbral'}`}
        />
        <Kpi label="Colonias en riesgo alto o brote" value={ranked.length} sub={`${nOut} en brote · de ${cols.length} colonias vigiladas`} />
        <Kpi label="Positividad de ovitrampas (IPO)" value={`${k.ipo}%`} sub={`${k.ipo_delta >= 0 ? '+' : ''}${k.ipo_delta} puntos vs. 7 días previos`} />
        <Kpi label="Nodos IoT en línea" value={`${k.nodes_online}/${k.nodes_total}`} sub={`${k.nodes_offline} sin datos en 48 h · revisar`} />
        <Kpi label="Reportes ciudadanos validados" value={k.reports_validated} sub={`últimos 7 días · ${k.reports_valid_pct}% con foto válida`} />
        <Kpi label="Lecturas IoT recibidas (24 h)" value={fmt(k.readings_24h)} sub={`última ${timeAgo(k.last_reading_at, now)}`} />
      </KpiRow>

      <Row>
        <Panel label="Mapa de riesgo" grow>
          <PanelHead title="Riesgo de brote por colonia · Mérida" right={`Pronóstico a ${H_LABELS[h]} · ${nOut} en brote, ${ranked.length - nOut} en alto`} />
          <div style={{ overflowX: 'auto' }}>
            <div role="group" aria-label="Colonias de Mérida, norte arriba" style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(108px, 1fr))', gridTemplateRows: 'repeat(5, 92px)', gap: 6, minWidth: 580 }}>
              {cols.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setSel(c.id)}
                  aria-label={`${c.name}: riesgo ${LEVELS[c.l]}, ${c.pH}% de probabilidad de brote`}
                  style={{
                    gridRow: c.gr, gridColumn: c.gc, background: BGS[c.l], color: FGS[c.l],
                    border: c.id === sc.id ? `3px solid ${C.teal}` : '1px solid rgba(23,33,31,0.12)',
                    borderRadius: 8, padding: '8px 10px', textAlign: 'left', cursor: 'pointer',
                    display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minWidth: 0,
                  }}
                >
                  <span style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.2 }}>{c.name}</span>
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 1, fontSize: 11.5, lineHeight: 1.25 }}>
                    <span style={{ ...mono, fontWeight: 500 }}>{c.pH}%</span>
                    {layers.ovi && <span>{c.eggs} huevos/trampa</span>}
                    {layers.crd && <span>{c.crd} criaderos</span>}
                    {layers.rain && <span>{c.rain} mm en 14 días</span>}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <RiskLegend extra={<span>Mapa esquemático, norte arriba. Toca una colonia.</span>} />
        </Panel>

        <aside aria-label="Detalle de colonia" style={{ flex: '1 1 320px', minWidth: 0, ...card, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <p style={{ margin: 0, fontSize: 12, color: C.muted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Colonia seleccionada</p>
            <h2 style={{ margin: '4px 0 0', fontSize: 22, fontWeight: 700 }}>{sc.name}</h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12, borderRadius: 10, background: BGS[sc.l], color: FGS[sc.l] }}>
            <span style={{ fontSize: 34, fontWeight: 700, ...mono }}>{sc.pH}%</span>
            <span style={{ fontSize: 13, lineHeight: 1.35 }}>
              <strong style={{ display: 'block', fontSize: 15 }}>Riesgo {LEVELS[sc.l]}</strong>probabilidad de brote en {H_LABELS[h]}
            </span>
          </div>
          <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 12px', fontSize: 13 }}>
            <div><dt style={{ color: C.muted }}>IPO de la colonia</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{sc.ipo}%</dd></div>
            <div><dt style={{ color: C.muted }}>Criaderos reportados</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{sc.crd} en 7 días</dd></div>
            <div><dt style={{ color: C.muted }}>Nodos IoT en línea</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{sc.nodes.online} de {sc.nodes.total}</dd></div>
            <div><dt style={{ color: C.muted }}>Lluvia (14 d) · T. mín.</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{sc.rain} mm · {sc.tmin} °C</dd></div>
            <div style={{ gridColumn: '1 / -1' }}>
              <dt style={{ color: C.muted }}>Huevecillos promedio por trampa, últimas 4 semanas</dt>
              <dd style={{ margin: '2px 0 0', fontWeight: 600, ...mono }}>{sc.trend.join(' → ')}</dd>
            </div>
          </dl>
          <Drivers drivers={sc.drivers} />
          <AssignBlock
            action={ACTIONS[sc.l]}
            assigned={sc.assigned}
            assignment={sc.assignment}
            busy={busy === sc.key}
            onAssign={() => onAssign(sc)}
            label="Asignar brigada de control"
            doneText="Brigada asignada · se notificó a la jurisdicción sanitaria"
          />
        </aside>
      </Row>

      <Row>
        <Panel label="Pronóstico" grow style={{ gap: 8 }}>
          <PanelHead title={title} right="Casos probables semanales, Yucatán" />
          <ForecastChart f={f} hIdx={hIdx} />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, fontSize: 12.5, color: C.muted }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="22" height="8" aria-hidden="true"><line x1="0" x2="22" y1="4" y2="4" stroke={C.ink} strokeWidth="2.25" /></svg>Observado
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="22" height="8" aria-hidden="true"><line x1="0" x2="22" y1="4" y2="4" stroke={C.teal} strokeWidth="2.25" strokeDasharray="5 3" /></svg>
              Pronóstico (tendencia de casos + huevecillos como indicador adelantado)
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 18, height: 10, background: C.teal, opacity: 0.25 }} />Intervalo de confianza 90%
            </span>
          </div>
        </Panel>

        <Panel label="Alertas y priorización" style={{ gap: 10 }}>
          <PanelHead title="Alertas y prioridad de brigadas" right={`${ranked.length} colonias en alto o brote`} />
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {ranked.slice(0, 7).map((c, i) => (
              <li key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 10, border: `1px solid ${C.soft}`, borderRadius: 10, padding: '8px 10px' }}>
                <span style={{ ...mono, fontSize: 12, color: C.muted, width: 18 }}>{i + 1}</span>
                <LevelTag level={LEVELS[c.l].toUpperCase()} bg={BGS[c.l]} fg={FGS[c.l]} />
                <button type="button" onClick={() => setSel(c.id)} style={{ flex: 1, minWidth: 0, border: 0, background: 'none', padding: '6px 0', textAlign: 'left', cursor: 'pointer', fontSize: 13.5, fontWeight: 600, color: C.ink }}>
                  {c.name} <span style={{ fontWeight: 400, color: C.muted }}>· {c.pH}%</span>
                </button>
                {c.assigned ? (
                  <span style={{ fontSize: 12, fontWeight: 600, color: C.green }}>Asignada</span>
                ) : (
                  <button
                    type="button"
                    disabled={busy === c.key}
                    onClick={() => onAssign(c)}
                    aria-label={`Asignar brigada a ${c.name}`}
                    style={{ border: `1px solid ${C.teal}`, background: '#FFFFFF', color: C.teal, borderRadius: 8, padding: '6px 10px', minHeight: 36, fontSize: 12.5, fontWeight: 600, cursor: 'pointer' }}
                  >
                    {busy === c.key ? 'Enviando…' : 'Asignar'}
                  </button>
                )}
              </li>
            ))}
            {ranked.length === 0 && <li style={{ fontSize: 13, color: C.muted }}>Ninguna colonia en riesgo alto o brote para este horizonte.</li>}
          </ul>
          <div style={{ borderTop: `1px solid ${C.soft}`, paddingTop: 10, fontSize: 12.5, color: C.muted, lineHeight: 1.5 }}>
            <strong style={{ color: C.ink }}>Canales:</strong> riesgo alto → jurisdicción y brigadas (push, SMS, correo). Brote → SSY, hospitales de la zona, ayuntamiento y vecinos (WhatsApp, SMS). Cada brigada asignada genera una orden de servicio en el ERP de la SSY.
          </div>
        </Panel>
      </Row>

      <footer style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 24px', fontSize: 12, color: C.muted }}>
        <span>Modelo de riesgo: logístico calibrado (prototipo del gradient boosting) · recalculado con cada lectura</span>
        <span>Fuentes: clima Open-Meteo, casos {data.meta.cases_source}, red de ovitrampas IoT (simulada), reportes ciudadanos</span>
        <span>Casos por colonia agregados por AGEB, sin datos personales</span>
      </footer>
    </>
  );
}
