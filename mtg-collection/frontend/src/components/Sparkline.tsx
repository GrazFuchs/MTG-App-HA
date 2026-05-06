import { useId } from 'react';
import { sothera } from '../theme/sothera';

const formatEur = (v: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(v);

/**
 * Sothera-styled sparkline with galaxy-foil gradient fill.
 * Accepts either { trend: number }[] (legacy) or { v: number; date?: string }[] data.
 */
export function Sparkline({
  data,
  width = 720,
  height = 140,
  accent,
  formatValue = formatEur,
  dot = true,
  dateLabels,
}: {
  data: ({ trend: number } | { v: number; date?: string })[];
  width?: number;
  height?: number;
  accent?: string;
  formatValue?: (v: number) => string;
  dot?: boolean;
  dateLabels?: [string, string];
}) {
  const uid = useId().replace(/:/g, '');
  if (data.length < 2) return <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgFaint }}>—</span>;

  const values = data.map(d => ('trend' in d ? d.trend : d.v));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const accentColor = accent || sothera.fgMuted;

  // Derive date labels from data if available and not explicitly passed
  const dates: [string, string] | null = dateLabels || (() => {
    const first = data[0];
    const last = data[data.length - 1];
    const d1 = 'date' in first ? (first as { date: string }).date : null;
    const d2 = 'date' in last ? (last as { date: string }).date : null;
    if (d1 && d2) return [d1.replace(/-/g, '.').slice(2), d2.replace(/-/g, '.').slice(2)];
    return null;
  })();

  const labelH = dates ? 20 : 0;
  const plotH = height;
  const totalH = plotH + labelH;

  const path = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = plotH - ((v - min) / range) * (plotH - 8) - 4;
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');

  const lastX = width;
  const lastY = plotH - ((values[values.length - 1] - min) / range) * (plotH - 8) - 4;
  const area = path + ` L ${width} ${plotH} L 0 ${plotH} Z`;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${totalH}`} style={{ display: 'block' }}>
      <defs>
        {/* Galaxy-foil gradient fill under the line */}
        <linearGradient id={`spark-fill-${uid}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={accentColor} style={{ stopOpacity: 'var(--sv-foil-top-opacity)' }} />
          <stop offset="50%" style={{ stopColor: 'var(--sv-foil-s2)', stopOpacity: '0.12' }} />
          <stop offset="100%" stopColor={accentColor} stopOpacity="0" />
        </linearGradient>
        {/* Grid pattern */}
        <pattern id={`spark-grid-${uid}`} width="60" height={plotH / 4} patternUnits="userSpaceOnUse">
          <path d={`M 60 0 L 0 0 0 ${plotH / 4}`} fill="none" stroke={sothera.rowBorder} strokeWidth="1" />
        </pattern>
      </defs>
      <rect x="0" y="0" width={width} height={plotH} fill={`url(#spark-grid-${uid})`} />
      <path d={area} fill={`url(#spark-fill-${uid})`} />
      <path d={path} fill="none" stroke={accentColor} strokeWidth="1.5" />
      {/* Invisible hit-area circles with tooltip */}
      {values.map((v, i) => {
        const x = (i / (values.length - 1)) * width;
        const y = plotH - ((v - min) / range) * (plotH - 8) - 4;
        return (
          <circle key={i} cx={x} cy={y} r={4} fill="transparent" stroke="transparent">
            <title>{formatValue(v)}</title>
          </circle>
        );
      })}
      {dot && (
        <>
          <circle cx={lastX} cy={lastY} r="3" fill={accentColor} />
          <circle cx={lastX} cy={lastY} r="9" fill="none" stroke={accentColor} opacity="0.45" />
          <circle cx={lastX} cy={lastY} r="14" fill="none" stroke={accentColor} opacity="0.18" />
        </>
      )}
      {dates && (
        <>
          <text x="0" y={plotH + 16} fontSize="9" fill={sothera.fgFaint} letterSpacing="1.5" fontFamily="JetBrains Mono">
            {dates[0]}
          </text>
          <text x={width} y={plotH + 16} fontSize="9" fill={sothera.fgFaint} letterSpacing="1.5" textAnchor="end" fontFamily="JetBrains Mono">
            {dates[1]}
          </text>
        </>
      )}
    </svg>
  );
}
