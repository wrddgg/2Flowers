import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/library': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/mock': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
