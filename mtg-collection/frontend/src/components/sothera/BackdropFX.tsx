import { sothera, type AccentDef } from '../../theme/sothera';

interface BackdropFXProps {
  accent: AccentDef;
}

export function BackdropFX({ accent }: BackdropFXProps) {
  return (
    <div
      aria-hidden
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
        overflow: 'hidden',
        background: sothera.bgGrad(accent),
      }}
    >
      {/* Fine star dust */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: `radial-gradient(1px 1px at 12% 18%, rgba(255,255,255,0.65), transparent),
            radial-gradient(1px 1px at 27% 64%, rgba(255,255,255,0.55), transparent),
            radial-gradient(1px 1px at 41% 32%, rgba(255,255,255,0.5), transparent),
            radial-gradient(1.4px 1.4px at 58% 12%, rgba(255,255,255,0.85), transparent),
            radial-gradient(1px 1px at 67% 78%, rgba(180,200,255,0.7), transparent),
            radial-gradient(1px 1px at 82% 22%, rgba(255,220,180,0.6), transparent),
            radial-gradient(1px 1px at 91% 58%, rgba(255,255,255,0.6), transparent),
            radial-gradient(2px 2px at 8% 88%, rgba(180,200,255,0.4), transparent),
            radial-gradient(1px 1px at 50% 92%, rgba(255,255,255,0.5), transparent),
            radial-gradient(1px 1px at 73% 6%, rgba(255,255,255,0.55), transparent)`,
          backgroundSize: '900px 900px',
          opacity: 0.6,
        }}
      />
      {/* Mid-density tiny dots */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: 'radial-gradient(0.5px 0.5px at 1px 1px, rgba(255,255,255,0.5), transparent 1px)',
          backgroundSize: '4px 4px',
          opacity: 0.18,
        }}
      />
      {/* Large nebula glow */}
      <div
        style={{
          position: 'absolute',
          top: '8%',
          left: '50%',
          width: 1200,
          height: 800,
          transform: 'translateX(-50%)',
          background: 'radial-gradient(ellipse 50% 50% at 50% 50%, oklch(0.65 0.20 295 / 0.18) 0%, transparent 70%)',
          filter: 'blur(20px)',
        }}
      />
      {/* Horizon haze */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: 240,
          background: 'linear-gradient(180deg, transparent 0%, rgba(40,30,80,0.18) 100%)',
        }}
      />
    </div>
  );
}
