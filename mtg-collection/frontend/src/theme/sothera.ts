import {
  createDarkTheme,
  createLightTheme,
  type BrandVariants,
  type Theme,
} from '@fluentui/react-components';

/**
 * "Sothera Vault" theme — Edge of Eternities space-opera design direction.
 *
 * Named accent families (oklch, single chroma each):
 *   sothera   dark: oklch(0.72 0.20 320)  light: oklch(0.52 0.20 320)
 *   nebula    dark: oklch(0.78 0.16 270)  light: oklch(0.52 0.18 270)
 *   endstone  dark: oklch(0.82 0.14 195)  light: oklch(0.50 0.16 220)
 *   stellar   dark: oklch(0.86 0.10 90)   light: oklch(0.62 0.14 75)
 *   drift     dark: oklch(0.78 0.18 145)  light: oklch(0.52 0.20 145)
 *   ember     dark: oklch(0.74 0.18 30)   light: oklch(0.55 0.20 30)
 */

export type ThemeMode = 'auto' | 'dark' | 'light';

// ── Accent definitions ──────────────────────────────────────────────

export type AccentName = 'sothera' | 'nebula' | 'endstone' | 'stellar' | 'drift' | 'ember';

export interface AccentDef {
  oklch: string;
  hex: string;       // closest hex fallback
  soft: string;      // 10% alpha variant
  glow: string;      // 45% alpha variant
  label: string;
}

/** Dark-mode accent variants (bright, high-chroma) */
export const ACCENTS: Record<AccentName, AccentDef> = {
  sothera:  { oklch: 'oklch(0.72 0.20 320)', hex: '#c850c0', soft: 'oklch(0.72 0.20 320 / 0.10)', glow: 'oklch(0.72 0.20 320 / 0.45)', label: 'Sothera' },
  nebula:   { oklch: 'oklch(0.78 0.16 270)', hex: '#9b8ec4', soft: 'oklch(0.78 0.16 270 / 0.10)', glow: 'oklch(0.78 0.16 270 / 0.45)', label: 'Nebula' },
  endstone: { oklch: 'oklch(0.82 0.14 195)', hex: '#5ec4c0', soft: 'oklch(0.82 0.14 195 / 0.10)', glow: 'oklch(0.82 0.14 195 / 0.45)', label: 'Endstone' },
  stellar:  { oklch: 'oklch(0.86 0.10 90)',  hex: '#d4c080', soft: 'oklch(0.86 0.10 90 / 0.10)',  glow: 'oklch(0.86 0.10 90 / 0.45)',  label: 'Stellar' },
  drift:    { oklch: 'oklch(0.78 0.18 145)', hex: '#52c47c', soft: 'oklch(0.78 0.18 145 / 0.10)', glow: 'oklch(0.78 0.18 145 / 0.45)', label: 'Drift' },
  ember:    { oklch: 'oklch(0.74 0.18 30)',  hex: '#d47040', soft: 'oklch(0.74 0.18 30 / 0.10)',  glow: 'oklch(0.74 0.18 30 / 0.45)',  label: 'Ember' },
};

/** Light-mode accent variants (darkened for AA contrast on #F4F5FA) */
export const ACCENTS_LIGHT: Record<AccentName, AccentDef> = {
  sothera:  { oklch: 'oklch(0.52 0.20 320)', hex: '#7a2978', soft: 'oklch(0.52 0.20 320 / 0.10)', glow: 'oklch(0.52 0.20 320 / 0.35)', label: 'Sothera' },
  nebula:   { oklch: 'oklch(0.52 0.18 270)', hex: '#5a3a8c', soft: 'oklch(0.52 0.18 270 / 0.10)', glow: 'oklch(0.52 0.18 270 / 0.35)', label: 'Nebula' },
  endstone: { oklch: 'oklch(0.50 0.16 220)', hex: '#1a6080', soft: 'oklch(0.50 0.16 220 / 0.10)', glow: 'oklch(0.50 0.16 220 / 0.35)', label: 'Endstone' },
  stellar:  { oklch: 'oklch(0.62 0.14 75)',  hex: '#8a6c00', soft: 'oklch(0.62 0.14 75 / 0.10)',  glow: 'oklch(0.62 0.14 75 / 0.35)',  label: 'Stellar' },
  drift:    { oklch: 'oklch(0.52 0.20 145)', hex: '#1a7840', soft: 'oklch(0.52 0.20 145 / 0.10)', glow: 'oklch(0.52 0.20 145 / 0.35)', label: 'Drift' },
  ember:    { oklch: 'oklch(0.55 0.20 30)',  hex: '#b84020', soft: 'oklch(0.55 0.20 30 / 0.10)',  glow: 'oklch(0.55 0.20 30 / 0.35)',  label: 'Ember' },
};

// ── Brand ramp — dark (sothera magenta-void) ────────────────────────

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

// ── Brand ramp — light (darkened for AA on white) ───────────────────

const sotheraBrandLight: BrandVariants = {
  10:  '#fdf0fd',
  20:  '#f9e0f9',
  30:  '#f0c4f0',
  40:  '#e4a4e4',
  50:  '#d080d0',
  60:  '#b85eb8',
  70:  '#9e3e9c',
  80:  '#842284',
  90:  '#6a0c6a',
  100: '#540054',
  110: '#400040',
  120: '#300030',
  130: '#240024',
  140: '#1a001a',
  150: '#110011',
  160: '#080008',
};

// ── Theme construction ──────────────────────────────────────────────

const baseTheme = createDarkTheme(sotheraBrand);
const baseLightTheme = createLightTheme(sotheraBrandLight);

export const sotheraTheme: Theme = {
  ...baseTheme,
  colorNeutralBackground1:        '#04040A',
  colorNeutralBackground1Hover:   '#0c0c18',
  colorNeutralBackground1Pressed: '#080810',
  colorNeutralBackground1Selected:'#0c0c18',
  colorNeutralBackground2:        '#08081A',
  colorNeutralBackground3:        '#0e0e24',
  colorNeutralBackground4:        '#141432',
  colorNeutralBackground6:        'rgba(20,20,32,0.55)',
  colorNeutralForeground1:        '#EDEDF5',
  colorNeutralForeground2:        '#9A9AB0',
  colorNeutralForeground3:        '#5E5E78',
  colorNeutralForeground4:        '#3A3A4E',
  colorNeutralStroke1:            'rgba(255,255,255,0.10)',
  colorNeutralStroke2:            'rgba(255,255,255,0.07)',
  colorNeutralStroke3:            'rgba(255,255,255,0.04)',
  colorNeutralStrokeAccessible:   'rgba(255,255,255,0.07)',
  fontFamilyBase: '"Inter", system-ui, -apple-system, sans-serif',
  fontFamilyMonospace: '"JetBrains Mono", "Fira Mono", monospace',
  fontFamilyNumeric: '"Space Grotesk", "Inter", system-ui, sans-serif',
};

export const sotheraLightTheme: Theme = {
  ...baseLightTheme,
  colorNeutralBackground1:        '#F4F5FA',
  colorNeutralBackground1Hover:   '#EAEDF5',
  colorNeutralBackground1Pressed: '#E0E4F0',
  colorNeutralBackground1Selected:'#EAEDF5',
  colorNeutralBackground2:        '#F0F2F8',
  colorNeutralBackground3:        '#EAEDF5',
  colorNeutralBackground4:        '#E4E8F4',
  colorNeutralBackground6:        'rgba(255,255,255,0.72)',
  colorNeutralForeground1:        '#0E1024',
  colorNeutralForeground2:        '#4A4D63',
  colorNeutralForeground3:        '#7B7E94',
  colorNeutralForeground4:        '#B0B3C4',
  colorNeutralStroke1:            'rgba(15,18,40,0.14)',
  colorNeutralStroke2:            'rgba(15,18,40,0.10)',
  colorNeutralStroke3:            'rgba(15,18,40,0.05)',
  colorNeutralStrokeAccessible:   'rgba(15,18,40,0.18)',
  fontFamilyBase: '"Inter", system-ui, -apple-system, sans-serif',
  fontFamilyMonospace: '"JetBrains Mono", "Fira Mono", monospace',
  fontFamilyNumeric: '"Space Grotesk", "Inter", system-ui, sans-serif',
};

// ── Design tokens (CSS-in-JS) ───────────────────────────────────────
// All color values are CSS custom property references — they resolve
// at runtime based on :root[data-sv-theme] set by SotheraThemeProvider.

export const sothera = {
  // Background
  bg: 'var(--sv-bg)',
  /** Dynamic nebula gradient — pass isDark so light variant applies masking */
  bgGrad: (accent: AccentDef, isDark = true) => isDark
    ? `radial-gradient(ellipse 70% 50% at 18% -10%, ${accent.soft} 0%, transparent 55%),
       radial-gradient(ellipse 50% 60% at 110% 30%, oklch(0.78 0.16 270 / 0.08) 0%, transparent 55%),
       radial-gradient(ellipse 80% 40% at 50% 110%, oklch(0.82 0.14 195 / 0.05) 0%, transparent 60%),
       linear-gradient(180deg, #04040A 0%, #06061A 50%, #04040A 100%)`
    : `radial-gradient(ellipse 50% 40% at 50% 0%, ${accent.soft} 0%, transparent 60%),
       radial-gradient(ellipse 40% 30% at 90% 5%, oklch(0.55 0.18 270 / 0.12) 0%, transparent 50%),
       linear-gradient(180deg, #F4F5FA 0%, #EEF0FA 50%, #F4F5FA 100%)`,

  // Galaxy-foil gradient (CSS var — switches per theme)
  foil: 'var(--sv-foil)',

  // Glass surface
  glassBg: 'var(--sv-surface)',
  glassBorder: 'var(--sv-border)',
  rowBorder: 'var(--sv-grid-line)',
  headerBorder: 'var(--sv-border-strong)',

  // Text
  fg: 'var(--sv-fg)',
  fgMuted: 'var(--sv-fg-muted)',
  fgFaint: 'var(--sv-fg-faint)',
  fgFainter: 'var(--sv-fg-fainter)',

  // Semantic
  positive: 'var(--sv-positive)',
  positiveSoft: 'var(--sv-positive-soft)',
  negative: 'var(--sv-negative)',
  negativeSoft: 'var(--sv-negative-soft)',

  // Type (static — same across themes)
  fontDisplay: '"Space Grotesk", system-ui, sans-serif',
  fontBody: '"Inter", system-ui, sans-serif',
  fontMono: '"JetBrains Mono", monospace',
} as const;

