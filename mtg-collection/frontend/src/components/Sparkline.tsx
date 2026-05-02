import { Caption1 } from '@fluentui/react-components';

const formatEur = (v: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(v);

export function Sparkline({
  data,
  width = 120,
  height = 32,
  formatValue = formatEur,
}: {
  data: { trend: number }[];
  width?: number;
  height?: number;
  formatValue?: (v: number) => string;
}) {
  if (data.length < 2) return <Caption1>—</Caption1>;
  const values = data.map(d => d.trend);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const LABEL_H = 14; // reserved px at bottom for first/last labels
  const plotH = height - LABEL_H;

  const coords = values.map((v, i) => ({
    x: (i / (values.length - 1)) * width,
    y: plotH - ((v - min) / range) * (plotH - 4) - 2,
    v,
  }));

  const points = coords.map(c => `${c.x},${c.y}`).join(' ');
  const color = values[values.length - 1] > values[0] ? '#d32f2f' : '#2e7d32';

  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
      {/* Invisible hit-area circles with native tooltip on each data point */}
      {coords.map((c, i) => (
        <circle key={i} cx={c.x} cy={c.y} r={4} fill="transparent" stroke="transparent">
          <title>{formatValue(c.v)}</title>
        </circle>
      ))}
      {/* First value label */}
      <text
        x={coords[0].x}
        y={height}
        textAnchor="start"
        fontSize={9}
        fill={color}
        opacity={0.8}
      >
        {formatValue(values[0])}
      </text>
      {/* Last value label */}
      <text
        x={coords[coords.length - 1].x}
        y={height}
        textAnchor="end"
        fontSize={9}
        fill={color}
        opacity={0.8}
      >
        {formatValue(values[values.length - 1])}
      </text>
    </svg>
  );
}
