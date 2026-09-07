import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    proxy: {
      // Local dev only - the API runs on :8000, Vite on :5173. In
      // production the built bundle is served BY the API (see
      // poke_calc/api/main.py), so there's no cross-origin request at
      // all there; this proxy just avoids needing CORS-aware fetch code
      // that only matters in dev.
      '/api': 'http://localhost:8000',
    },
  },
})
