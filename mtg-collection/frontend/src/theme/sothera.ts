import {
  createDarkTheme,
  type BrandVariants,
  type Theme,
} from '@fluentui/react-components';

/**
 * "Sothera Vault" theme — Edge of Eternities space-opera design direction.
 *
 * Named accent families (oklch, single chroma each):
 *   sothera   oklch(0.72 0.20 320)  magenta-void, default
 *   nebula    oklch(0.78 0.16 270)  violet
 *   endstone  oklch(0.82 0.14 195)  cyan
 *   stellar   oklch(0.86 0.10 90)   gold
 *   drift     oklch(0.78 0.18 145)  toxic green
 *   ember     oklch(0.74 0.18 30)   mars red
 */

// ── Accent definitions ──────────────────────────────────────────────

export type AccentName = 'sothera' | 'nebula' | 'endstone' | 'stellar' | 'drift' | 'ember';

export interface AccentDef {
  oklch: string;
  hex: string;       // closest hex fallback
  soft: string;      // 10% alpha variant
  glow: string;      // 45% alpha variant
  label: string;
}

export const ACCENTS: Record<AccentName, AccentDef> = {
  sothera:  { oklch: 'oklch(0.72 0.20 320)', hex: '#c850c0', soft: 'oklch(0.72 0.20 320 / 0.10)', glow: 'oklch(0.72 0.20 320 / 0.45)', label: 'Sothera' },
  nebula:   { oklch: 'oklch(0.78 0.16 270)', hex: '#9b8ec4', soft: 'oklch(0.78 0.16 270 / 0.10)', glow: 'oklch(0.78 0.16 270 / 0.45)', label: 'Nebula' },
  endstone: { oklch: 'oklch(0.82 0.14 195)', hex: '#5ec4c0', soft: 'oklch(0.82 0.14 195 / 0.10)', glow: 'oklch(0.82 0.14 195 / 0.45)', label: 'Endstone' },
  stellar:  { oklch: 'oklch(0.86 0.10 90)',  hex: '#d4c080', soft: 'oklch(0.86 0.10 90 / 0.10)',  glow: 'oklch(0.86 0.10 90 / 0.45)',  label: 'Stellar' },
  drift:    { oklch: 'oklch(0.78 0.18 145)', hex: '#52c47c', soft: 'oklch(0.78 0.18 145 / 0.10)', glow: 'oklch(0.78 0.18 145 / 0.45)', label: 'Drift' },
  ember:    { oklch: 'oklch(0.74 0.18 30)',  hex: '#d47040', soft: 'oklch(0.74 0.18 30 / 0.10)',  glow: 'oklch(0.74 0.18 30 / 0.45)',  label: 'Ember' },
};

// ── Brand ramp (Sothera magenta-void by default) ────────────────────
// Fluent expects 16 shades (10..160 by 10). Generated from sothera accent.

const sotheraBrand: BrandVariants = {
  10:  '#0a0410',
  20:  '#160820',
  30:  '#250c38',
  40:  '#34104c',
  50:  '#441462',
  60:  '#551878',
  70:  '#681c90',
  80:  '#7c22a8',
  90:  '#9030b8',
  100: '#a840c4',
  110: '#b854cc',
  120: '#c868d4',
  130: '#d480dc',
  140: '#de98e4',
  150: '#e8b0ec',
  160: '#f2ccf4',
};

// ── Theme construction ──────────────────────────────────────────────

const baseTheme = createDarkTheme(sotheraBrand);

export const sotheraTheme: Theme = {
  ...baseTheme,
  // Override neutral backgrounds to the deep void palette
  colorNeutralBackground1:        '#04040A',
  colorNeutralBackground1Hover:   '#0c0c18',
  colorNeutralBackground1Pressed: '#080810',
  colorNeutralBackground1Selected:'#0c0c18',
  colorNeutralBackground2:        '#08081A',
  colorNeutralBackground3:        '#0e0e24',
  colorNeutralBackground4:        '#141432',
  // Surface / glass effect (used by Card, etc.)
  colorNeutralBackground6:        'rgba(20,20,32,0.55)',
  // Subtle foreground overrides
  colorNeutralForeground1:        '#EDEDF5',
  colorNeutralForeground2:        '#9A9AB0',
  colorNeutralForeground3:        '#5E5E78',
  colorNeutralForeground4:        '#3A3A4E',
  // Stroke tones
  colorNeutralStroke1:            'rgba(255,255,255,0.10)',
  colorNeutralStroke2:            'rgba(255,255,255,0.07)',
  colorNeutralStroke3:            'rgba(255,255,255,0.04)',
  // Surface borders (glass)
  colorNeutralStrokeAccessible:   'rgba(255,255,255,0.07)',
  // Font families
  fontFamilyBase: '"Inter", system-ui, -apple-system, sans-serif',
  fontFamilyMonospace: '"JetBrains Mono", "Fira Mono", monospace',
  fontFamilyNumeric: '"Space Grotesk", "Inter", system-ui, sans-serif',
};

// ── Design tokens (CSS-in-JS) ───────────────────────────────────────

export const sothera = {
  // Background
  bg: '#04040A',
  bgGrad: (accent: AccentDef) =>
    `radial-gradient(ellipse 70% 50% at 18% -10%, ${accent.soft} 0%, transparent 55%),
     radial-gradient(ellipse 50% 60% at 110% 30%, oklch(0.78 0.16 270 / 0.08) 0%, transparent 55%),
     radial-gradient(ellipse 80% 40% at 50% 110%, oklch(0.82 0.14 195 / 0.05) 0%, transparent 60%),
     linear-gradient(180deg, #04040A 0%, #06061A 50%, #04040A 100%)`,

  // Galaxy-foil gradient
  foil: `linear-gradient(120deg,
    oklch(0.32 0.10 290) 0%,
    oklch(0.55 0.22 320) 30%,
    oklch(0.62 0.20 270) 55%,
    oklch(0.72 0.16 200) 80%,
    oklch(0.70 0.14 170) 100%)`,

  // Glass surface
  glassBg: 'rgba(20,20,32,0.55)',
  glassBorder: 'rgba(255,255,255,0.07)',
  rowBorder: 'rgba(255,255,255,0.04)',
  headerBorder: 'rgba(255,255,255,0.12)',

  // Text
  fg: '#EDEDF5',
  fgMuted: '#9A9AB0',
  fgFaint: '#5E5E78',
  fgFainter: '#3A3A4E',

  // Semantic
  positive: 'oklch(0.78 0.17 150)',
  positiveSoft: 'oklch(0.78 0.17 150 / 0.10)',
  negative: 'oklch(0.70 0.20 25)',
  negativeSoft: 'oklch(0.70 0.20 25 / 0.10)',

  // Type
  fontDisplay: '"Space Grotesk", system-ui, sans-serif',
  fontBody: '"Inter", system-ui, sans-serif',
  fontMono: '"JetBrains Mono", monospace',
} as const;
