// ConfidenceGuard operations console, served by `confidenceguard ops serve` at /ops/ and shipped prebuilt as
// package data. In development the API is proxied to a local `ops serve` (NUMEK_OPS_API, default 127.0.0.1:8443).
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const api = process.env.NUMEK_OPS_API ?? 'http://127.0.0.1:8443';

export default defineConfig({
  root: resolve(__dirname, 'ops'),
  base: '/ops/',
  publicDir: false,
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5322, strictPort: true, fs: { allow: [__dirname] }, proxy: { '/api': api } },
  build: {
    outDir: resolve(__dirname, '../src/confidenceguard/static/ops'),
    emptyOutDir: true,
    assetsInlineLimit: 0,
    rollupOptions: { input: resolve(__dirname, 'ops/index.html') },
  },
});
