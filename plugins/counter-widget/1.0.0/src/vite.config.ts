import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: '../ui',
    emptyOutDir: false,
    lib: {
      entry: resolve(__dirname, 'index.ts'),
      name: 'CounterWidget',
      formats: ['es'],
      fileName: 'index',
    },
    rollupOptions: {
      // Vue is provided by the host (window.Vue) — do not bundle it
      external: ['vue'],
      output: {
        globals: { vue: 'Vue' },
      },
    },
  },
})
