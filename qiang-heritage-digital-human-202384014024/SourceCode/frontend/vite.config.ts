/* Vite React build configuration; no development API proxy is configured.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
/*
 * Build/dev-server configuration.
 *
 * No `server.proxy` entry is declared on purpose: every API call in src/api/chat.ts is built
 * from `window.location.origin`, and in production the FastAPI backend serves the compiled
 * `dist/` bundle from the same host, so requests such as `/chat`, `/tts`, and
 * `/knowledge-base/*` reach the backend without a rewrite. Adding a proxy would only be needed
 * if the frontend were run on a different port during development.
 */
export default defineConfig({
  plugins: [react()],
})
