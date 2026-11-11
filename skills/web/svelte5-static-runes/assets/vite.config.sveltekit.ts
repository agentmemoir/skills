import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';
import adapter from '@sveltejs/adapter-static';

// SvelteKit 3 + adapter-static static build (no server at request time).
// SvelteKit 3 removed svelte.config.js: these options go in the sveltekit() plugin.
// On the 2.x line, put the same options under `kit` in svelte.config.js.
// Using SCSS or other preprocessors in .svelte files? Add `preprocess: vitePreprocess()`
// (from '@sveltejs/vite-plugin-svelte') to the sveltekit() options.
export default defineConfig({
  plugins: [
    sveltekit({
      adapter: adapter({
        pages: 'build',
        assets: 'build',
        // SPA mode: uncomment the next line ONLY if the app has no +page.server.js /
        // +server.js anywhere and you accept the SEO/no-JS tradeoffs (see references/static-build.md)
        // fallback: 'index.html',
        precompress: false,
        strict: true
      })
      // GitHub Pages project site (not a custom domain or user/org root page):
      // paths: { base: process.env.BASE_PATH ?? '' }
    })
  ],
  build: {
    sourcemap: true // safe for a static site; omit only if you don't want source visible to consumers
  }
});
