import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './frontend'),
      '@view': resolve(__dirname, './frontend/views')
    }
  },
  test: {
    globals: true,
    environment: 'happy-dom'
  }
})