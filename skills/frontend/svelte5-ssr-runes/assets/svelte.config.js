import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),

  // Async SSR + remote functions are experimental (await expressions: Svelte 5.36+;
  // async SSR: Svelte 5.39.3+ with SvelteKit 2.43+).
  // Leave off unless the user explicitly asks; see references/runes-ssr.md.
  // compilerOptions: { experimental: { async: true } },

  kit: {
    adapter: adapter(),
    // Swap for @sveltejs/adapter-node (self-hosted), adapter-cloudflare, adapter-vercel, etc.

    // CSP: SvelteKit adds nonces (dynamic pages) or hashes (prerendered pages) to
    // the inline scripts/styles it generates. Manual tags in src/app.html need
    // nonce="%sveltekit.nonce%". Start reportOnly, then promote to enforce.
    csp: {
      mode: 'auto',
      directives: {
        'default-src': ['self'],
        'script-src': ['self'],
        // Svelte transitions inject inline <style> elements; keep this while they exist.
        'style-src': ['self', 'unsafe-inline'],
        'img-src': ['self', 'data:', 'https:'],
        'connect-src': ['self'],
        'object-src': ['none'],
        'base-uri': ['self'],
        'frame-ancestors': ['self']
      }
    },

    // CSRF origin checks for form submissions are on by default (production only).
    // Only add trustedOrigins when a trusted third party really posts to your app.
    csrf: { trustedOrigins: [] }

    // Env: PUBLIC_-prefixed vars reach the browser; everything else stays server-only.
    // See references/security.md before changing the prefixes.
  }
};

export default config;
