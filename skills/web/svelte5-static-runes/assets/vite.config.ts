import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Plain Vite + Svelte 5 static build (no SvelteKit, no server).
// `npm run build` outputs a fully static `dist/` folder — upload as-is to any static host/CDN.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: 'dist',
    sourcemap: true // safe for a static site; omit only if you don't want source visible to consumers
  }
  // Only env vars prefixed with VITE_ are exposed to client code — see references/security.md
  // before adding anything under `define` or `.env` that must stay secret.
});
