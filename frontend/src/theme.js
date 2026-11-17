export const LEVELS = ['bajo', 'moderado', 'alto', 'brote'];
export const BGS = ['#E3EEE6', '#F4D88A', '#E07A2E', '#9E1F1A'];
export const FGS = ['#17211F', '#17211F', '#17211F', '#FFFFFF'];
export const H_LABELS = ['1 semana', '2 semanas', '4 semanas'];
export const H_FORECAST_IDX = [0, 1, 3]; // índice del pronóstico semanal para 1, 2 y 4 semanas

export const lv = (p) => (p < 25 ? 0 : p < 50 ? 1 : p < 75 ? 2 : 3);

export const C = {
  ink: '#17211F',
  muted: '#4A5754',
  line: '#D5DCDA',
  soft: '#E3E8E6',
  teal: '#0F5C6E',
  bg: '#F4F6F5',
  green: '#1E6B3A',
  red: '#9E1F1A',
  orange: '#B4531A',
};

export const card = {
  background: '#FFFFFF',
  border: `1px solid ${C.line}`,
  borderRadius: 12,
  padding: 16,
};

export const mono = { fontFamily: "'IBM Plex Mono', monospace" };

export function timeAgo(iso, now = Date.now()) {
  if (!iso) return 'sin datos';
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return `hace ${s} s`;
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  return `hace ${Math.round(s / 86400)} d`;
}

export const clock = (iso) =>
  iso ? new Date(iso).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';

export const fmt = (n) => (typeof n === 'number' ? n.toLocaleString('es-MX') : n);
