import { useState } from 'react';
import { BGS, C, FGS, LEVELS, lv } from '../theme.js';

const MSGS = [
  'Hay pocos mosquitos en tu colonia. Sigue revisando tu patio cada semana.',
  'Está aumentando el mosquito en tu colonia. Es buen momento para limpiar tu patio.',
  'Hay muchos huevecillos de mosquito en tu colonia y podría haber casos de dengue pronto.',
  'Es muy probable un brote de dengue en tu colonia. Actúa hoy y protege a tu familia.',
];
const ACTS = [
  ['Revisa y vacía recipientes con agua una vez por semana', 'Tapa tinacos y tambos'],
  ['Vacía, voltea o tapa todo recipiente con agua', 'Lava con cepillo bebederos y floreros', 'Deja abrir tu casa a la brigada de salud'],
  ['Vacía, voltea o tapa todo recipiente con agua hoy', 'Usa repelente, sobre todo al amanecer y al atardecer', 'Coloca mosquiteros en puertas y ventanas', 'Reporta criaderos en la calle o terrenos baldíos'],
  ['Vacía, voltea o tapa todo recipiente con agua hoy mismo', 'Usa repelente todo el día, en especial niñas, niños y adultos mayores', 'Duerme con mosquitero', 'Ante fiebre, acude de inmediato a tu centro de salud'],
];

const box = { background: '#FFFFFF', border: `1px solid ${C.line}`, borderRadius: 14, padding: 20, display: 'flex', flexDirection: 'column' };
const field = { fontFamily: 'inherit', fontSize: 14, padding: 10, border: '1px solid #B9C4C1', borderRadius: 8 };

export default function CitView({ data, cit, setCit, onReport }) {
  const cc = data.colonias.find((c) => c.id === cit) || data.colonias[0];
  const cp = cc.p[1];
  const cl = lv(cp);
  const [desc, setDesc] = useState('');
  const [file, setFile] = useState(null);
  const [sent, setSent] = useState(null);
  const [sending, setSending] = useState(false);
  const sms =
    `Riesgo ${LEVELS[cl].toUpperCase()} de dengue en ${cc.name} las próximas 2 semanas. ` +
    (cl >= 2 ? 'Vacía y tapa recipientes con agua hoy y usa repelente.' : 'Revisa tu patio y vacía recipientes con agua.') +
    ' Ver mapa y qué hacer: [enlace]';

  const submit = async () => {
    setSending(true);
    const r = await onReport({ colonia: cc.id, descripcion: desc, con_foto: !!file });
    setSending(false);
    if (r) {
      setSent(r);
      setDesc('');
      setFile(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'flex-start', justifyContent: 'center' }}>
      <section aria-label="Riesgo en tu colonia" style={{ flex: '999 1 520px', minWidth: 0, maxWidth: 720, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ ...box, gap: 14 }}>
          <label htmlFor="colonia" style={{ fontSize: 14, fontWeight: 600 }}>¿En qué colonia vives?</label>
          <select id="colonia" value={cc.id} onChange={(e) => setCit(e.target.value)} style={{ ...field, fontSize: 15, padding: '10px 12px', minHeight: 44, background: '#FFFFFF', color: C.ink }}>
            {data.colonias.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <div style={{ borderRadius: 12, padding: 18, background: BGS[cl], color: FGS[cl] }}>
            <p style={{ margin: 0, fontSize: 13, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Próximas 2 semanas</p>
            <p style={{ margin: '6px 0 4px', fontSize: 30, fontWeight: 700 }}>Riesgo {LEVELS[cl]}</p>
            <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.45 }}>{MSGS[cl]}</p>
          </div>
          <div>
            <h2 style={{ margin: '0 0 8px', fontSize: 16, fontWeight: 600 }}>Qué hacer esta semana</h2>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14.5, lineHeight: 1.6 }}>
              {ACTS[cl].map((t) => <li key={t}>{t}</li>)}
            </ul>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: C.muted }}>Si tienes fiebre, dolor de cuerpo o detrás de los ojos, acude a tu centro de salud. No te automediques.</p>
        </div>

        <div style={{ ...box, gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Reporta un criadero</h2>
          {!sent ? (
            <>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5, color: C.muted }}>Un tambo destapado, llantas con agua o un pozo pluvial tapado. Tu foto ayuda a que la brigada llegue antes.</p>
              <label htmlFor="foto" style={{ fontSize: 13.5, fontWeight: 600 }}>Foto del criadero</label>
              <input id="foto" type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} style={{ fontFamily: 'inherit', fontSize: 13.5 }} />
              <label htmlFor="nota" style={{ fontSize: 13.5, fontWeight: 600 }}>Descripción (opcional)</label>
              <textarea id="nota" rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Ejemplo: llantas con agua en el terreno baldío de la esquina" style={{ ...field, resize: 'vertical' }} />
              <p style={{ margin: 0, fontSize: 12.5, color: C.muted }}>
                Usamos tu ubicación redondeada a 100 metros. Las caras y placas se difuminan de forma automática. En este prototipo la foto no se sube: solo se registra que el reporte trae evidencia.
              </p>
              <button type="button" disabled={sending} onClick={submit} style={{ alignSelf: 'flex-start', border: 0, background: C.teal, color: '#FFFFFF', borderRadius: 8, padding: '12px 18px', minHeight: 44, fontSize: 15, fontWeight: 600, cursor: 'pointer' }}>
                {sending ? 'Enviando…' : 'Enviar reporte'}
              </button>
            </>
          ) : (
            <>
              <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: C.green }}>Gracias. Tu reporte llegó a la Secretaría de Salud.</p>
              <p style={{ margin: 0, fontSize: 14, color: C.muted }}>
                Te avisaremos cuando una brigada lo atienda. Folio: <span className="mono">{sent.folio}</span>
                {sent.status === 'pendiente' && ' · sin foto, queda pendiente de validar'}
              </p>
              <button type="button" onClick={() => setSent(null)} style={{ alignSelf: 'flex-start', border: `1px solid ${C.teal}`, background: '#FFFFFF', color: C.teal, borderRadius: 8, padding: '10px 16px', minHeight: 44, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                Reportar otro
              </button>
            </>
          )}
        </div>
      </section>

      <aside aria-label="Ejemplo de alerta en el teléfono" style={{ flex: '1 1 300px', maxWidth: 340, display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: C.muted }}>Así llega la alerta al teléfono</p>
        <div style={{ width: 'min(300px, 100%)', borderRadius: 36, background: C.ink, padding: 14 }}>
          <div style={{ borderRadius: 26, background: '#E9EEEC', padding: '40px 12px 120px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ background: '#FFFFFF', borderRadius: 16, padding: '12px 14px', boxShadow: '0 1px 2px rgba(0,0,0,0.08)' }}>
              <p style={{ margin: '0 0 4px', fontSize: 11.5, fontWeight: 700, color: C.teal, letterSpacing: '0.04em' }}>SENTINELA AEDES · SSY</p>
              <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.4 }}>{sms}</p>
            </div>
            <div style={{ background: '#FFFFFF', borderRadius: 16, padding: '12px 14px', boxShadow: '0 1px 2px rgba(0,0,0,0.08)' }}>
              <p style={{ margin: '0 0 4px', fontSize: 11.5, fontWeight: 700, color: C.teal, letterSpacing: '0.04em' }}>SENTINELA AEDES · MAAYA T'AAN</p>
              <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.4 }}>[Mensaje equivalente en lengua maya, traducido y validado por hablantes de la comunidad]</p>
            </div>
          </div>
        </div>
        <p style={{ margin: 0, fontSize: 12.5, color: C.muted, textAlign: 'center' }}>También por SMS, radio comunitaria y perifoneo para quien no tiene smartphone.</p>
      </aside>
    </div>
  );
}
