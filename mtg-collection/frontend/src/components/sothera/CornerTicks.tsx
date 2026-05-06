import { sothera } from '../../theme/sothera';

interface CornerTicksProps {
  color?: string;
}

export function CornerTicks({ color }: CornerTicksProps) {
  const c = color || sothera.fgFaint;
  const len = 12;
  const tick = (top: boolean, left: boolean): React.CSSProperties => ({
    position: 'absolute',
    [top ? 'top' : 'bottom']: -1,
    [left ? 'left' : 'right']: -1,
  });

  return (
    <>
      <span style={{ ...tick(true, true), width: len, height: 1, background: c }} />
      <span style={{ ...tick(true, true), width: 1, height: len, background: c }} />
      <span style={{ ...tick(true, false), width: len, height: 1, background: c }} />
      <span style={{ ...tick(true, false), width: 1, height: len, background: c }} />
      <span style={{ ...tick(false, true), width: len, height: 1, background: c }} />
      <span style={{ ...tick(false, true), width: 1, height: len, background: c }} />
      <span style={{ ...tick(false, false), width: len, height: 1, background: c }} />
      <span style={{ ...tick(false, false), width: 1, height: len, background: c }} />
    </>
  );
}
