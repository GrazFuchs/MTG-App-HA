import React, { useState, createContext, useContext } from 'react';
import ReactDOM from 'react-dom/client';
import { FluentProvider } from '@fluentui/react-components';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { sotheraTheme, ACCENTS, type AccentName, type AccentDef } from './theme/sothera';
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

// Accent context for swapping accent colors across the app
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

function Root() {
  const [accentName, setAccentName] = useState<AccentName>(
    () => (localStorage.getItem('sothera-accent') as AccentName) || 'sothera'
  );
  const accent = ACCENTS[accentName] || ACCENTS.sothera;

  const setAccent = (name: AccentName) => {
    setAccentName(name);
    localStorage.setItem('sothera-accent', name);
  };

  return (
    <AccentContext.Provider value={{ accent, accentName, setAccent }}>
      <FluentProvider theme={sotheraTheme}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter basename={basePath}>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </FluentProvider>
    </AccentContext.Provider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
