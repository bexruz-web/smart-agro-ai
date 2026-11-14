/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Backend (FastAPI) runs on :8000 in development. "/api" is the REST API,
  // "/tg" is the Telegram bot webhook path (proxied so a single HTTPS tunnel works).
  const backend = env.VITE_DEV_BACKEND || 'http://localhost:8000'

  return {
    plugins: [react()],
    // Relative asset paths: the app works from any sub-path behind nginx.
    base: './',
    server: {
      host: true,
      port: 5173,
      // Allow access through HTTPS tunnels (cloudflared / ngrok) used for Telegram testing.
      allowedHosts: true,
      proxy: {
        '/api': { target: backend, changeOrigin: true },
        '/tg': { target: backend, changeOrigin: true },
      },
    },
    build: {
      sourcemap: false,
      chunkSizeWarningLimit: 1500,
    },
    test: {
      environment: 'node',
      include: ['src/**/*.test.ts'],
    },
  }
})
