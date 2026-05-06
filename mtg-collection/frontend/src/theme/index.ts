import React, { createContext, useContext, useState, useEffect } from 'react';
import type { Theme } from '@fluentui/react-components';
import { sotheraTheme, sotheraLightTheme, type ThemeMode } from './sothera';

export type { ThemeMode } from './sothera';

// ── Context shape ───────────────────────────────────────────────────

interface SotheraThemeCtx {
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  isDark: boolean;
  fluentTheme: Theme;
}

const SotheraThemeContext = createContext<SotheraThemeCtx>({
  mode: 'dark',
  setMode: () => {},
  isDark: true,
  fluentTheme: sotheraTheme,
});

export const useSotheraTheme = () => useContext(SotheraThemeContext);

// ── Resolution helper ───────────────────────────────────────────────

function resolveIsDark(mode: ThemeMode): boolean {
  if (mode === 'dark') return true;
  if (mode === 'light') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function applyThemeAttribute(isDark: boolean) {
  document.documentElement.dataset.svTheme = isDark ? 'dark' : 'light';
}

// ── Provider ────────────────────────────────────────────────────────

export function SotheraThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(
    () => (localStorage.getItem('sothera.theme') as ThemeMode) || 'auto'
  );
  const [isDark, setIsDark] = useState(() => {
    const initial = (localStorage.getItem('sothera.theme') as ThemeMode) || 'auto';
    return resolveIsDark(initial);
  });

  const setMode = (m: ThemeMode) => {
    localStorage.setItem('sothera.theme', m);
    const dark = resolveIsDark(m);
    setModeState(m);
    setIsDark(dark);
    applyThemeAttribute(dark);
  };

  // Re-apply attribute whenever mode changes, and register system listener
  useEffect(() => {
    const dark = resolveIsDark(mode);
    setIsDark(dark);
    applyThemeAttribute(dark);

    if (mode !== 'auto') return;

    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => {
      const d = mq.matches;
      setIsDark(d);
      applyThemeAttribute(d);
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [mode]);

  const fluentTheme = isDark ? sotheraTheme : sotheraLightTheme;

  return React.createElement(
    SotheraThemeContext.Provider,
    { value: { mode, setMode, isDark, fluentTheme } },
    children
  );
}
