import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Repository-subpath safe: relative asset URLs, HashRouter in app.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
  publicDir: 'public'
})
