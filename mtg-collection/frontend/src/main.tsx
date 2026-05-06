import React, { useState, createContext, useContext } from 'react';
import ReactDOM from 'react-dom/client';
import { FluentProvider } from '@fluentui/react-components';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { ACCENTS, ACCENTS_LIGHT, type AccentName, type AccentDef } from './theme/sothera';
import { SotheraThemeProvider, useSotheraTheme } from './theme';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

// HA ingress: extract /api/hassio_ingress/<token> from the path
const basePath = (() => {
  const path = window.location.pathname;
  const match = path.match(/^(\/api\/hassio_ingress\/[^/]+)/);
  if (match) return match[1];
  return '/';
})();

// Accent context — provides the active theme's accent variant
interface AccentCtx {
  accent: AccentDef;
  accentName: AccentName;
  setAccent: (name: AccentName) => void;
}
const AccentContext = createContext<AccentCtx>({
  accent: ACCENTS.sothera,
  accentName: 'sothera',
  setAccent: () => {},
});
export const useAccent = () => useContext(AccentContext);

// Inner component: reads theme mode to pick the right accent variant
function AccentProvider({ accentName, setAccent, children }: {
  accentName: AccentName;
  setAccent: (name: AccentName) => void;
  children: React.ReactNode;
}) {
  const { isDark } = useSotheraTheme();
  const accents = isDark ? ACCENTS : ACCENTS_LIGHT;
  const accent = accents[accentName] || accents.sothera;
  return (
    <AccentContext.Provider value={{ accent, accentName, setAccent }}>
      {children}
    </AccentContext.Provider>
  );
}

// Inner component: reads fluentTheme from context
function ThemedApp() {
  const { fluentTheme } = useSotheraTheme();
  return (
    <FluentProvider theme={fluentTheme}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename={basePath}>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </FluentProvider>
  );
}

function Root() {
  const [accentName, setAccentName] = useState<AccentName>(
    () => (localStorage.getItem('sothera-accent') as AccentName) || 'sothera'
  );

  const setAccent = (name: AccentName) => {
    setAccentName(name);
    localStorage.setItem('sothera-accent', name);
  };

  return (
    <SotheraThemeProvider>
      <AccentProvider accentName={accentName} setAccent={setAccent}>
        <ThemedApp />
      </AccentProvider>
    </SotheraThemeProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);

