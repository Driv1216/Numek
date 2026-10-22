// Static marketing site: / (NUMEK) and /datatrust/ (DataTrust page). Deployable to any static host.
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: resolve(__dirname, 'site'),
  base: '/',
  publicDir: false,
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5320, strictPort: true, fs: { allow: [__dirname] } },
  build: {
    outDir: resolve(__dirname, 'dist/site'),
    emptyOutDir: true,
    assetsInlineLimit: 0,
    // The Drop and the mosaic drawings ship the validation run's packed rows (about 320 kB).
    chunkSizeWarningLimit: 700,
    rollupOptions: { input: { index: resolve(__dirname, 'site/index.html'), datatrust: resolve(__dirname, 'site/datatrust/index.html') } },
  },
});
