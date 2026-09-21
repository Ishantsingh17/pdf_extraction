import { defineConfig, type PluginOption } from 'vite'
import react from '@vitejs/plugin-react'

/** Extraction is a single long request: the browser holds `POST /api/v1/documents`
 *  open until OCR, layout analysis and extraction have all finished. Node's
 *  http.Server aborts any request older than `requestTimeout` (5 minutes by
 *  default) with a body-less 408, which reaches the UI as the generic
 *  "Something went wrong." With the Paddle engines a multi-page scan can pass
 *  that, so the dev server is told not to time the upload out. */
const allowLongUploads: PluginOption = {
  name: 'allow-long-uploads',
  configureServer(server) {
    if (server.httpServer) server.httpServer.requestTimeout = 0
  },
}

export default defineConfig({
  plugins: [react(), allowLongUploads],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Same reason: no socket timeout on either leg of the proxied request.
        timeout: 0,
        proxyTimeout: 0,
      },
    },
  },
})
