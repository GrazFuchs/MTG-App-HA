import React from 'react';
import ReactDOM from 'react-dom/client';
import { FluentProvider, webLightTheme, webDarkTheme } from '@fluentui/react-components';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
// HA ingress: extract /api/hassio_ingress/<token> from the path (stable on sub-pages)
const basePath = (() => {
  const path = window.location.pathname;
  const match = path.match(/^(\/api\/hassio_ingress\/[^/]+)/);
  if (match) return match[1];
  return '/';
})();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <FluentProvider theme={prefersDark ? webDarkTheme : webLightTheme}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename={basePath}>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </FluentProvider>
  </React.StrictMode>
);
