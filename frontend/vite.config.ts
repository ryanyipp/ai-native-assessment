import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The browser only talks to the FlowLens backend; model calls stay server-side.
// FLOWLENS_API_URL and FRONTEND_PORT override the defaults (e.g. a second checkout or Docker).
const api = process.env.FLOWLENS_API_URL || 'http://127.0.0.1:8000'
const port = Number(process.env.FRONTEND_PORT || 5173)

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port, strictPort: true, proxy: { '/api': api } },
  preview: { port, strictPort: true, proxy: { '/api': api } },
})
