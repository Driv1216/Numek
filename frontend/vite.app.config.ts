// Local DataTrust app, served by Flask at /app/ and shipped prebuilt as package data.
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: resolve(__dirname, 'app'),
  base: '/app/',
  publicDir: false,
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5321, strictPort: true, fs: { allow: [__dirname] } },
  build: {
    outDir: resolve(__dirname, '../src/datatrust/static/app'),
    emptyOutDir: true,
    assetsInlineLimit: 0,
    rollupOptions: { input: resolve(__dirname, 'app/index.html') },
  },
});
