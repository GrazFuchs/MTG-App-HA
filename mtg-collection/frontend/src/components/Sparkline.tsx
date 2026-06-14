import { useId, useRef, useState } from 'react';
import { sothera } from '../theme/sothera';

const formatEur = (v: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(v);

type SparkPoint = { trend: number } | { v: number; date?: string };

const pointValue = (d: SparkPoint) => ('trend' in d ? d.trend : d.v);
const pointDate = (d: SparkPoint): string | undefined =>
  'date' in d ? (d as { date?: string }).date : undefined;

/**
 * Sothera-styled sparkline with galaxy-foil gradient fill.
 * Accepts either { trend: number }[] (legacy) or { v: number; date?: string }[] data.
 *
 * Pass `interactive` to enable a cursor-following crosshair that shows the
 * value (and date, if present) at the nearest datapoint.
 */
export function Sparkline({
  data,
  width = 720,
  height = 140,
  accent,
  formatValue = formatEur,
  dot = true,
  dateLabels,
  interactive = false,
}: {
  data: SparkPoint[];
  width?: number;
  height?: number;
  accent?: string;
  formatValue?: (v: number) => string;
  dot?: boolean;
  dateLabels?: [string, string];
  interactive?: boolean;
}) {
  const uid = useId().replace(/:/g, '');
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  if (data.length < 2) return <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgFaint }}>—</span>;

  const values = data.map(pointValue);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const accentColor = accent || sothera.fgMuted;

  // Derive date labels from data if available and not explicitly passed
  const dates: [string, string] | null = dateLabels || (() => {
    const d1 = pointDate(data[0]);
    const d2 = pointDate(data[data.length - 1]);
    if (d1 && d2) return [d1.replace(/-/g, '.').slice(2), d2.replace(/-/g, '.').slice(2)];
    return null;
  })();

  const labelH = dates ? 20 : 0;
  const plotH = height;
  const totalH = plotH + labelH;

  const xAt = (i: number) => (i / (values.length - 1)) * width;
  const yAt = (v: number) => plotH - ((v - min) / range) * (plotH - 8) - 4;

  const path = values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`).join(' ');

  const lastX = width;
  const lastY = yAt(values[values.length - 1]);
  const area = path + ` L ${width} ${plotH} L 0 ${plotH} Z`;

  const handleMove = (e: React.MouseEvent) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    const rel = (e.clientX - rect.left) / rect.width;
    const idx = Math.max(0, Math.min(values.length - 1, Math.round(rel * (values.length - 1))));
    setHoverIdx(idx);
  };

  const hx = hoverIdx != null ? xAt(hoverIdx) : 0;
  const hy = hoverIdx != null ? yAt(values[hoverIdx]) : 0;
  const hoverDate = hoverIdx != null ? pointDate(data[hoverIdx]) : undefined;
  const labelText = hoverIdx != null
    ? `${formatValue(values[hoverIdx])}${hoverDate ? `  ${hoverDate.replace(/-/g, '.').slice(2)}` : ''}`
    : '';
  // Keep the label inside the viewport horizontally.
  const labelAnchor = hx > width * 0.6 ? 'end' : 'start';
  const labelX = labelAnchor === 'end' ? hx - 6 : hx + 6;

  return (
    <svg
      ref={svgRef}
      width="100%"
      viewBox={`0 0 ${width} ${totalH}`}
      style={{ display: 'block' }}
      onMouseMove={interactive ? handleMove : undefined}
      onMouseLeave={interactive ? () => setHoverIdx(null) : undefined}
    >
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
      {/* Non-interactive: native tooltips on invisible hit-areas */}
      {!interactive && values.map((v, i) => (
        <circle key={i} cx={xAt(i)} cy={yAt(v)} r={4} fill="transparent" stroke="transparent">
          <title>{formatValue(v)}</title>
        </circle>
      ))}
      {/* Interactive crosshair following the cursor */}
      {interactive && hoverIdx != null && (
        <g pointerEvents="none">
          <line x1={hx} y1={0} x2={hx} y2={plotH} stroke={accentColor} strokeWidth="1" opacity="0.4" />
          <circle cx={hx} cy={hy} r="3.5" fill={accentColor} />
          <text
            x={labelX}
            y={Math.max(11, hy - 6)}
            fontSize="11"
            fill={sothera.fg}
            textAnchor={labelAnchor}
            fontFamily="JetBrains Mono"
          >
            {labelText}
          </text>
        </g>
      )}
      {dot && !(interactive && hoverIdx != null) && (
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
