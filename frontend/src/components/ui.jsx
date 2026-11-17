import { BGS, C, card, mono } from '../theme.js';

export function Kpi({ label, value, sub, color }) {
  return (
    <div style={card}>
      <p style={{ margin: 0, fontSize: 12.5, color: C.muted, fontWeight: 500 }}>{label}</p>
      <p className="kpi-value" style={{ margin: '6px 0 2px', fontSize: 30, fontWeight: 700, ...mono, color: color || C.ink }}>
        {value}
      </p>
      <p style={{ margin: 0, fontSize: 12.5, color: C.muted }}>{sub}</p>
    </div>
  );
}

export function KpiRow({ children, label }) {
  return (
    <section aria-label={label} className="kpi-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12 }}>
      {children}
    </section>
  );
}

export function Panel({ label, children, grow = false, style }) {
  return (
    <section
      aria-label={label}
      style={{
        flex: grow ? '999 1 560px' : '1 1 320px',
        minWidth: 0,
        ...card,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        ...style,
      }}
    >
      {children}
    </section>
  );
}

export function Row({ children }) {
  return <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'stretch' }}>{children}</div>;
}

export function PanelHead({ title, right }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
      <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{title}</h2>
      {right != null && <span style={{ fontSize: 12.5, color: C.muted }}>{right}</span>}
    </div>
  );
}

export function RiskLegend({ extra }) {
  const sw = (bg, border) => (
    <span style={{ width: 14, height: 14, borderRadius: 3, background: bg, border: border || 'none', display: 'inline-block' }} />
  );
  const item = { display: 'flex', alignItems: 'center', gap: 6 };
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 14, fontSize: 12.5, color: C.muted }}>
      <span style={{ fontWeight: 600 }}>Probabilidad de brote</span>
      <span style={item}>{sw(BGS[0], '1px solid #B9CCBF')}Bajo · menos de 25%</span>
      <span style={item}>{sw(BGS[1])}Moderado · 25–49%</span>
      <span style={item}>{sw(BGS[2])}Alto · 50–74%</span>
      <span style={item}>{sw(BGS[3])}Brote · 75% o más</span>
      {extra}
    </div>
  );
}

export function HorizonPicker({ h, setH, labels }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: C.muted }}>Horizonte del pronóstico</span>
      {labels.map((label, i) => (
        <button
          key={label}
          type="button"
          aria-pressed={i === h}
          onClick={() => setH(i)}
          style={{
            border: `1px solid ${i === h ? C.teal : '#B9C4C1'}`,
            background: i === h ? C.teal : '#FFFFFF',
            color: i === h ? '#FFFFFF' : C.ink,
            borderRadius: 999,
            padding: '8px 14px',
            minHeight: 40,
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function LevelTag({ level, bg, fg }) {
  return (
    <span style={{ fontSize: 11.5, fontWeight: 700, borderRadius: 6, padding: '3px 7px', background: bg, color: fg }}>{level}</span>
  );
}

export function Drivers({ drivers }) {
  return (
    <div>
      <h3 style={{ margin: '0 0 6px', fontSize: 13.5, fontWeight: 600 }}>Qué explica el riesgo</h3>
      <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.5 }}>
        {drivers.map((d) => (
          <li key={d.key}>
            {d.text} <span style={{ color: C.muted }}>({d.weight})</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function AssignBlock({ action, assigned, assignment, onAssign, busy, label, doneText }) {
  return (
    <div style={{ borderTop: `1px solid ${C.soft}`, paddingTop: 12 }}>
      <h3 style={{ margin: '0 0 6px', fontSize: 13.5, fontWeight: 600 }}>Acción recomendada</h3>
      <p style={{ margin: '0 0 10px', fontSize: 13, lineHeight: 1.5 }}>{action}</p>
      {assigned ? (
        <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: C.green }}>
          {doneText}
          {assignment?.folio && (
            <span style={{ display: 'block', fontWeight: 500, color: C.muted, marginTop: 2 }}>
              Orden de servicio en el ERP: <span className="mono">{assignment.folio}</span>
            </span>
          )}
        </p>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={onAssign}
          style={{ border: 0, background: C.teal, color: '#FFFFFF', borderRadius: 8, padding: '10px 14px', minHeight: 44, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
        >
          {busy ? 'Enviando orden al ERP…' : label}
        </button>
      )}
    </div>
  );
}
