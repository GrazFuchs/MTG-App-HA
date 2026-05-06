interface SigilProps {
  size?: number;
  color: string;
  dim?: number;
}

export function Sigil({ size = 14, color, dim = 1 }: SigilProps) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        position: 'relative',
        opacity: dim,
        verticalAlign: 'middle',
      }}
    >
      <span
        style={{
          position: 'absolute',
          inset: 0,
          border: `1px solid ${color}`,
          transform: 'rotate(45deg)',
        }}
      />
      <span
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: size * 0.35,
          height: size * 0.35,
          transform: 'translate(-50%,-50%) rotate(45deg)',
          background: color,
        }}
      />
    </span>
  );
}
