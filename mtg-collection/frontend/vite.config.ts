import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    proxy: {
      '/api': 'http://localhost:8099',
      '/mcp': 'http://localhost:8099',
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
  test: {
    // jsdom, not node: without a DOM there can be no component test, and
    // without component tests the display bugs kept shipping — an unreachable
    // dialog, a popup behind the following cards, a duplicated table row. All
    // of them are things a render test sees and a unit test cannot.
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
    include: ['src/**/__tests__/**/*.test.{ts,tsx}'],
  },
});
