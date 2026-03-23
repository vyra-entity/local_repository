import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  build: {
    lib: {
      entry: resolve(__dirname, 'index.ts'),
      name: 'ModuleCountWidget',
      formats: ['es'],
      fileName: () => 'index.js',
    },
    outDir: '../ui',
    emptyOutDir: true,
    rollupOptions: {
      external: ['vue'],
      output: {
        globals: { vue: 'Vue' },
      },
    },
  },
})
