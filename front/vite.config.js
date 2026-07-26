import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true
      },
      '/library': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true
      },
      '/mock': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true
      }
    }
  }
})
