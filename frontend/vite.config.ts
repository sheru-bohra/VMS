import { resolve } from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  envDir: resolve(__dirname, '..'),
  plugins: [react()],
  build: {
    sourcemap: process.env.VITE_ENABLE_SOURCEMAPS === 'true',
  },
  server: {
    port: 7272,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:7273',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
});
