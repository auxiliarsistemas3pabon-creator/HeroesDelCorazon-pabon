import process from 'node:process'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // VITE_API_URL (en .env) = origen del backend, sin /api/v1 (ej. http://localhost:8000).
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react(), tailwindcss()],
    server: {
      // El front llama a /api/v1/... en su mismo origen (cookies httpOnly + CSRF sin CORS)
      // y Vite reenvía esas peticiones al backend.
      proxy: {
        '/api': env.VITE_API_URL || 'http://localhost:8000',
      },
    },
  }
})
