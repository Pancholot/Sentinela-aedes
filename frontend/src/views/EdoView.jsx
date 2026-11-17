import { AssignBlock, Drivers, HorizonPicker, Kpi, KpiRow, LevelTag, Panel, PanelHead, RiskLegend, Row } from '../components/ui.jsx';
import { BGS, C, FGS, H_LABELS, LEVELS, card, fmt, lv, mono } from '../theme.js';

const actionMun = (l, iot) =>
  [
    'Vigilancia de rutina con casos y clima.',
    'Reforzar promoción y revisar criaderos en 7 días' + (iot ? '.' : '; priorizar instalación de ovitrampas IoT.'),
    'Brigada de control larvario esta semana, aviso al ayuntamiento y alerta por SMS, radio comunitaria y perifoneo.',
    'Control larvario y nebulización en 48 horas, aviso al hospital de referencia y alerta a la población en español y maya.',
  ][l];

export default function EdoView({ data, h, setH, mun, setMun, onAssign, busy }) {
  const { kpis: k } = data;
  const muns = data.municipios.map((m) => ({ ...m, pH: m.p[h], l: lv(m.p[h]) }));
  const mc = muns.find((m) => m.id === mun) || muns[0];
  const ranked = muns.filter((m) => m.l >= 2).sort((a, b) => b.pH - a.pH);
  const nOut = ranked.filter((m) => m.l === 3).length;
  const hiMarg = muns.filter((m) => m.marg === 'Alta' || m.marg === 'Muy alta');

  return (
    <>
      <section aria-label="Controles del estado" style={{ ...card, padding: '12px 16px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <HorizonPicker h={h} setH={setH} labels={H_LABELS} />
        <span style={{ fontSize: 13, color: C.muted }}>
          Municipios con riesgo calculado: {muns.length} · los de borde punteado aún no tienen ovitrampas IoT
        </span>
      </section>

      <KpiRow label="Indicadores del estado">
        <Kpi label="Municipios en riesgo alto o brote" value={ranked.length} sub={`${nOut} en brote · ${ranked.filter((m) => !m.iot).length} sin ovitrampas IoT`} />
        <Kpi label="Casos probables, últimas 4 semanas" value={fmt(k.cases4_municipios)} sub={`en los ${muns.length} municipios mostrados`} />
        <Kpi label="Nodos rurales en línea" value={`${k.rural_online}/${k.rural_total}`} sub="NB-IoT y gateways en centros de salud" />
        <Kpi label="Riesgo alto o brote en marginación alta" value={`${hiMarg.filter((m) => m.l >= 2).length} de ${hiMarg.length}`} sub="municipios de marginación alta o muy alta" />
      </KpiRow>

      <Row>
        <Panel label="Mapa de riesgo por municipio" grow>
          <PanelHead title="Riesgo de brote por municipio · Yucatán" right={`Pronóstico a ${H_LABELS[h]} · ${nOut} en brote, ${ranked.length - nOut} en alto`} />
          <div style={{ overflowX: 'auto' }}>
            <div role="group" aria-label="Municipios de Yucatán, norte arriba" style={{ display: 'grid', gridTemplateColumns: 'repeat(6, minmax(100px, 1fr))', gridTemplateRows: 'repeat(4, 84px)', gap: 6, minWidth: 640 }}>
              {muns.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMun(m.id)}
                  aria-label={`${m.name}: riesgo ${LEVELS[m.l]}, ${m.pH}% de probabilidad de brote${m.iot ? '' : ', sin ovitrampas IoT'}`}
                  style={{
                    gridRow: m.gr, gridColumn: m.gc, background: BGS[m.l], color: FGS[m.l],
                    border: m.id === mc.id ? `3px solid ${C.teal}` : m.iot ? '1px solid rgba(23,33,31,0.12)' : '2px dashed rgba(23,33,31,0.55)',
                    borderRadius: 8, padding: '8px 10px', textAlign: 'left', cursor: 'pointer',
                    display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minWidth: 0,
                  }}
                >
                  <span style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.2 }}>{m.name}</span>
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 1, fontSize: 11.5, lineHeight: 1.25 }}>
                    <span style={{ ...mono, fontWeight: 500 }}>{m.pH}%</span>
                    <span>{m.iot ? `${m.nodes.online}/${m.nodes.total} nodos` : 'sin nodos IoT'}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
          <RiskLegend
            extra={
              <>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 14, height: 14, borderRadius: 3, border: `2px dashed ${C.muted}`, display: 'inline-block' }} />
                  Sin ovitrampas IoT (solo casos y clima)
                </span>
                <span>Mapa esquemático, norte arriba. Toca un municipio.</span>
              </>
            }
          />
        </Panel>

        <aside aria-label="Detalle de municipio" style={{ flex: '1 1 320px', minWidth: 0, ...card, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <p style={{ margin: 0, fontSize: 12, color: C.muted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Municipio seleccionado</p>
            <h2 style={{ margin: '4px 0 0', fontSize: 22, fontWeight: 700 }}>{mc.name}</h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12, borderRadius: 10, background: BGS[mc.l], color: FGS[mc.l] }}>
            <span style={{ fontSize: 34, fontWeight: 700, ...mono }}>{mc.pH}%</span>
            <span style={{ fontSize: 13, lineHeight: 1.35 }}>
              <strong style={{ display: 'block', fontSize: 15 }}>Riesgo {LEVELS[mc.l]}</strong>probabilidad de brote en {H_LABELS[h]}
            </span>
          </div>
          <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 12px', fontSize: 13 }}>
            <div><dt style={{ color: C.muted }}>Casos probables, 4 semanas</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{mc.cases_txt}</dd></div>
            <div><dt style={{ color: C.muted }}>Marginación (CONAPO)</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{mc.marg}</dd></div>
            <div><dt style={{ color: C.muted }}>Ovitrampas IoT</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{mc.iot ? `${mc.nodes.online} de ${mc.nodes.total} en línea` : 'Sin instalar'}</dd></div>
            <div><dt style={{ color: C.muted }}>Confianza del pronóstico</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{mc.conf}</dd></div>
            <div><dt style={{ color: C.muted }}>Lluvia últimos 14 días</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{mc.rain} mm</dd></div>
            <div><dt style={{ color: C.muted }}>Temperatura mínima</dt><dd style={{ margin: '2px 0 0', fontWeight: 600 }}>{mc.tmin} °C</dd></div>
          </dl>
          <Drivers drivers={mc.drivers} />
          <AssignBlock
            action={actionMun(mc.l, mc.iot)}
            assigned={mc.assigned}
            assignment={mc.assignment}
            busy={busy === mc.key}
            onAssign={() => onAssign(mc)}
            label="Asignar brigada al municipio"
            doneText="Brigada asignada · se notificó a la jurisdicción sanitaria y al ayuntamiento"
          />
        </aside>
      </Row>

      <Row>
        <Panel label="Prioridad por municipio" grow style={{ gap: 10 }}>
          <PanelHead title="Municipios prioritarios" right={`${ranked.length} municipios en alto o brote`} />
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {ranked.slice(0, 8).map((m, i) => (
              <li key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10, border: `1px solid ${C.soft}`, borderRadius: 10, padding: '8px 10px' }}>
                <span style={{ ...mono, fontSize: 12, color: C.muted, width: 18 }}>{i + 1}</span>
                <LevelTag level={LEVELS[m.l].toUpperCase()} bg={BGS[m.l]} fg={FGS[m.l]} />
                <button type="button" onClick={() => setMun(m.id)} style={{ flex: 1, minWidth: 0, border: 0, background: 'none', padding: '6px 0', textAlign: 'left', cursor: 'pointer', fontSize: 13.5, fontWeight: 600, color: C.ink }}>
                  {m.name}{' '}
                  <span style={{ fontWeight: 400, color: C.muted }}>
                    · {m.pH}% · marginación {String(m.marg).toLowerCase()}
                    {m.iot ? '' : ' · sin nodos'}
                  </span>
                </button>
                {m.assigned ? (
                  <span style={{ fontSize: 12, fontWeight: 600, color: C.green }}>Asignada</span>
                ) : (
                  <button
                    type="button"
                    disabled={busy === m.key}
                    onClick={() => onAssign(m)}
                    aria-label={`Asignar brigada a ${m.name}`}
                    style={{ border: `1px solid ${C.teal}`, background: '#FFFFFF', color: C.teal, borderRadius: 8, padding: '6px 10px', minHeight: 36, fontSize: 12.5, fontWeight: 600, cursor: 'pointer' }}
                  >
                    {busy === m.key ? 'Enviando…' : 'Asignar'}
                  </button>
                )}
              </li>
            ))}
            {ranked.length === 0 && <li style={{ fontSize: 13, color: C.muted }}>Ningún municipio en riesgo alto o brote para este horizonte.</li>}
          </ul>
        </Panel>

        <Panel label="Auditoría de sesgos">
          <div>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Auditoría de sesgos · {data.audit[0]?.period}</h2>
            <p style={{ margin: '4px 0 0', fontSize: 12.5, color: C.muted }}>Sensibilidad del modelo para detectar brotes, por tipo de zona. Meta: 80% o más en todas.</p>
          </div>
          {data.audit.map((a) => {
            const color = a.v >= 80 ? C.green : C.orange;
            return (
              <div key={a.label} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span>{a.label}</span>
                  <span style={{ ...mono, fontWeight: 600, color }}>{a.v}%</span>
                </div>
                <div style={{ height: 8, borderRadius: 4, background: C.soft, overflow: 'hidden' }}>
                  <div style={{ height: 8, width: `${a.v}%`, background: color }} />
                </div>
              </div>
            );
          })}
          <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: C.muted, borderTop: `1px solid ${C.soft}`, paddingTop: 10 }}>
            <strong style={{ color: C.ink }}>Hallazgo:</strong> las zonas de marginación alta quedan por debajo de la meta porque tienen menos pruebas de laboratorio. Acción: el modelo usa casos probables y en el 4.º trimestre se agregan 20 nodos en esos municipios.
          </p>
        </Panel>
      </Row>

      <footer style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 24px', fontSize: 12, color: C.muted }}>
        <span>Pronóstico municipal: modelo logístico con casos, clima real, huevecillos y marginación</span>
        <span>Fuentes: casos {data.meta.cases_source}, clima Open-Meteo, CONAPO, red de ovitrampas IoT (simulada)</span>
        <span>Casos agregados por municipio; menos de 5 casos se muestra como "menos de 5"</span>
      </footer>
    </>
  );
}
