import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';
import { createReadStream } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import type { Plugin } from 'vite';
import { previewAssets } from './src/api/previewAssets';

function lectureDocuments(): Plugin {
  const docsRoot = new URL('../docs/', import.meta.url);
  const names = new Set<string>(previewAssets.map(asset => asset.filename));
  return {
    name: 'immutable-lecture-documents',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        if (!request.url?.startsWith('/docs/')) return next();
        let name: string;
        try { name = decodeURIComponent(new URL(request.url, 'http://localhost').pathname.slice(6)); }
        catch { response.statusCode = 400; response.end(); return; }
        if (!names.has(name) || !['GET', 'HEAD'].includes(request.method || '')) {
          response.statusCode = 404; response.end(); return;
        }
        const path = fileURLToPath(new URL(name, docsRoot));
        void stat(path).then(info => {
          response.setHeader('Content-Type', 'application/pdf');
          response.setHeader('X-Content-Type-Options', 'nosniff');
          response.setHeader('Content-Length', info.size);
          if (request.method === 'HEAD') { response.end(); return; }
          const stream = createReadStream(path);
          stream.on('error', () => response.destroy());
          stream.pipe(response);
        }).catch(() => { response.statusCode = 404; response.end(); });
      });
    },
    async generateBundle() {
      for (const name of names) {
        this.emitFile({ type: 'asset', fileName: `docs/${name}`, source: await readFile(new URL(name, docsRoot)) });
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), lectureDocuments()],
  build: { rollupOptions: { output: { manualChunks: {
    react: ['react', 'react-dom'], fluent: ['@fluentui/react-components'], markdown: ['react-markdown', 'remark-gfm'],
  } } } },
  server: {
    host: true, allowedHosts: true, strictPort: false,
    proxy: { '/api': { target: process.env.WORKSHOP_API_URL || 'http://127.0.0.1:8000',
      changeOrigin: true, rewrite: path => path.replace(/^\/api/, '') } },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/testSetup.ts'], restoreMocks: true },
});