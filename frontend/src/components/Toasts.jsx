import { C } from '../theme.js';

const STYLES = {
  pending: { border: '#B9C4C1', icon: '…', iconBg: '#E3E8E6', iconFg: C.ink },
  ok: { border: '#9CCBAE', icon: '✓', iconBg: '#1E6B3A', iconFg: '#FFFFFF' },
  error: { border: '#E2A48A', icon: '!', iconBg: '#9E1F1A', iconFg: '#FFFFFF' },
};

// Alertas flotantes: muestran el envío de documentos al ERP (simulado).
export default function Toasts({ items, onClose }) {
  return (
    <div
      aria-live="polite"
      style={{ position: 'fixed', right: 16, bottom: 16, left: 16, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8, zIndex: 50, pointerEvents: 'none' }}
    >
      {items.map((t) => {
        const s = STYLES[t.kind] || STYLES.ok;
        return (
          <div
            key={t.id}
            className="toast"
            role="status"
            style={{ pointerEvents: 'auto', width: 'min(420px, 100%)', background: '#FFFFFF', border: `1px solid ${s.border}`, borderRadius: 12, boxShadow: '0 6px 20px rgba(23,33,31,0.14)', padding: '12px 14px', display: 'flex', gap: 12, alignItems: 'flex-start' }}
          >
            <span style={{ flex: '0 0 26px', height: 26, borderRadius: 13, background: s.iconBg, color: s.iconFg, display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 14 }}>
              {s.icon}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ margin: 0, fontSize: 11.5, fontWeight: 700, letterSpacing: '0.05em', color: C.teal }}>{t.tag || 'INTEGRACIÓN ERP'}</p>
              <p style={{ margin: '2px 0 0', fontSize: 14, fontWeight: 600 }}>{t.title}</p>
              {t.body && <p style={{ margin: '2px 0 0', fontSize: 12.5, color: C.muted, lineHeight: 1.4, overflowWrap: 'anywhere' }}>{t.body}</p>}
            </div>
            <button type="button" aria-label="Cerrar aviso" onClick={() => onClose(t.id)} style={{ border: 0, background: 'none', fontSize: 18, lineHeight: 1, color: C.muted, cursor: 'pointer', padding: 2 }}>
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}
