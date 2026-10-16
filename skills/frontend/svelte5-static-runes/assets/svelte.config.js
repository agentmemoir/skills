import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      // SPA mode: uncomment the next line ONLY if the app has no +page.server.js /
      // +server.js anywhere and you accept the SEO/no-JS tradeoffs (see references/static-build.md)
      // fallback: 'index.html',
      precompress: false,
      strict: true
    })
    // If deploying to a GitHub Pages project site (not a custom domain or user/org root page):
    // paths: { base: process.env.BASE_PATH ?? '' }
  }
};

export default config;
