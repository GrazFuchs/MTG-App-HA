import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { FluentProvider, webLightTheme, webDarkTheme } from '@fluentui/react-components';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

// Detect HA dark mode: check HA body attribute, then CSS media query fallback
function getIsDark(): boolean {
  const ha = document.body.getAttribute('data-theme');
  if (ha === 'dark') return true;
  if (ha === 'light') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

// HA ingress: extract /api/hassio_ingress/<token> from the path
const basePath = (() => {
  const path = window.location.pathname;
  const match = path.match(/^(\/api\/hassio_ingress\/[^/]+)/);
  if (match) return match[1];
  return '/';
})();

function Root() {
  const [dark, setDark] = useState(getIsDark);

  useEffect(() => {
    // React to OS-level prefers-color-scheme changes
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => setDark(getIsDark());
    mq.addEventListener('change', handler);

    // Observe HA data-theme attribute mutations on <body>
    const observer = new MutationObserver(() => setDark(getIsDark()));
    observer.observe(document.body, { attributes: true, attributeFilter: ['data-theme'] });

    return () => { mq.removeEventListener('change', handler); observer.disconnect(); };
  }, []);

  return (
    <FluentProvider theme={dark ? webDarkTheme : webLightTheme}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename={basePath}>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </FluentProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
