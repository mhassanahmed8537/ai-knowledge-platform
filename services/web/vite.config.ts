import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Same-origin from the browser's perspective in dev, matching how a
      // real deployment reverse-proxies the SPA and API behind one edge --
      // avoids needing CORS middleware on the API at all.
      // Regex key (not a literal '/api' prefix) so it only matches '/api/...'
      // — a bare string prefix would also swallow the '/api-keys' SPA route.
      '^/api/': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
