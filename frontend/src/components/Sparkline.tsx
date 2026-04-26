import { Caption1 } from '@fluentui/react-components';
import { PriceHistoryEntry } from '../api';

export function Sparkline({ data, width = 120, height = 32 }: { data: PriceHistoryEntry[]; width?: number; height?: number }) {
  if (data.length < 2) return <Caption1>—</Caption1>;
  const values = data.map(d => d.trend);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values.map((v, i) =>
    `${(i / (values.length - 1)) * width},${height - ((v - min) / range) * (height - 4) - 2}`
  ).join(' ');
  const color = values[values.length - 1] > values[0] ? '#d32f2f' : '#2e7d32';
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}
