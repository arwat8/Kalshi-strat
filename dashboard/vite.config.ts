import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' makes the build work at a domain root (Vercel) and under a sub-path (GitHub Pages).
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { target: 'es2020', chunkSizeWarningLimit: 900 },
});
