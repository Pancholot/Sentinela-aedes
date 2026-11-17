import { C } from '../theme.js';

// Curva de casos probables semanales (observado + pronóstico con intervalo de 90 %).
export default function ForecastChart({ f, hIdx }) {
  const n = f.observed.length;
  const total = n + f.mean.length;
  const X = (i) => 48 + i * (652 / (total - 1));
  const maxV = Math.max(...f.hi, ...f.observed, f.threshold);
  const ymax = Math.max(60, Math.ceil((maxV * 1.08) / 40) * 40);
  const Y = (v) => 230 - v * (210 / ymax);
  const pt = (i, v) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`;
  const last = f.observed[n - 1];

  const obs = f.observed.map((v, i) => pt(i, v)).join(' ');
  const fc = [pt(n - 1, last), ...f.mean.map((v, i) => pt(n + i, v))].join(' ');
  const band = [pt(n - 1, last), ...f.hi.map((v, i) => pt(n + i, v)), ...f.lo.map((v, i) => pt(n + i, v)).reverse()].join(' ');
  const fx = (X(n - 1) + X(n)) / 2;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((k) => Math.round(ymax * k));
  const xticks = Array.from({ length: total }, (_, i) => i).filter((i) => i % 2 === 0);
  const crossTxt = f.cross_week ? `cruza el umbral de ${f.threshold} casos en la semana ${f.cross_week}` : `se mantiene por debajo del umbral de ${f.threshold} casos`;

  return (
    <svg
      viewBox="0 0 720 270"
      role="img"
      aria-label={`Casos observados de la semana ${f.weeks[0]} a la ${f.weeks[n - 1]} y pronóstico de la ${f.weeks[n]} a la ${f.weeks[total - 1]} con intervalo de confianza; ${crossTxt}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
    >
      {ticks.map((v) => (
        <g key={v}>
          <line x1="48" x2="700" y1={Y(v)} y2={Y(v)} stroke={C.soft} strokeWidth="1" />
          <text x="40" y={Y(v) + 4} textAnchor="end" fontSize="11" fill={C.muted}>
            {v}
          </text>
        </g>
      ))}
      <rect x={fx} y="18" width={700 - fx} height="212" fill={C.teal} fillOpacity="0.05" />
      <text x={fx + 8} y="30" fontSize="11" fill={C.teal} fontWeight="600">
        Pronóstico
      </text>
      <polygon points={band} fill={C.teal} fillOpacity="0.16" />
      <line x1="48" x2="700" y1={Y(f.threshold)} y2={Y(f.threshold)} stroke={C.red} strokeWidth="1.5" strokeDasharray="6 4" />
      <text x="52" y={Y(f.threshold) - 6} fontSize="11" fill={C.red} fontWeight="600">
        Umbral epidémico (canal endémico simplificado): {f.threshold}
      </text>
      <polyline points={obs} fill="none" stroke={C.ink} strokeWidth="2.25" />
      <polyline points={fc} fill="none" stroke={C.teal} strokeWidth="2.25" strokeDasharray="7 5" />
      {f.observed.map((v, i) => (
        <circle key={`o${i}`} cx={X(i)} cy={Y(v)} r="3" fill={C.ink} stroke="#FFFFFF" strokeWidth="1.5">
          <title>{`Semana ${f.weeks[i]}: ${v} casos probables`}</title>
        </circle>
      ))}
      {f.mean.map((v, i) => (
        <circle key={`f${i}`} cx={X(n + i)} cy={Y(v)} r={i === hIdx ? 6 : 3.5} fill={v >= f.threshold ? C.red : C.teal} stroke="#FFFFFF" strokeWidth="1.5">
          <title>{`Semana ${f.weeks[n + i]}: ${v} casos pronosticados (${f.lo[i]}–${f.hi[i]})`}</title>
        </circle>
      ))}
      <text x={X(n + hIdx)} y={Math.max(14, Y(f.hi[hIdx]) - 10)} textAnchor="middle" fontSize="12" fontWeight="700" fill={C.teal}>
        {f.mean[hIdx]} casos
      </text>
      {xticks.map((i) => (
        <text key={i} x={X(i)} y="250" textAnchor="middle" fontSize="11" fill={C.muted}>
          S{f.weeks[i]}
        </text>
      ))}
    </svg>
  );
}
