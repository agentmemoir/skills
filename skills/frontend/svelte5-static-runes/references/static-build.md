# Static Builds for Svelte 5

Two supported shapes. Pick per the table in SKILL.md; details for each below.

## Option A — Plain Vite + Svelte (no SvelteKit)

This is a pure client-side SPA: one `index.html`, one JS bundle, no routing framework, no server anywhere in the picture (not even at build time beyond Vite itself). Best default for a single-page tool, dashboard, embeddable widget, or small app that doesn't need multiple routes.

```bash
npm create vite@latest my-app -- --template svelte-ts
cd my-app
npm install
npm run build   # outputs static files to dist/
```

`dist/` is the entire deliverable — upload it as-is to any static host or CDN. There is nothing further to configure for "static-only" because this template never had a server. If you need client-side routing across multiple "pages" without SvelteKit, add a lightweight router (e.g. `svelte-spa-router` or hand-rolled hash routing) — this keeps the whole app statically hostable with zero rewrite-rule configuration since hash routes don't need server-side URL rewriting.

If you need real path-based routes (`/about`, not `/#/about`) without a server, you'll need your static host to serve `index.html` for unknown paths (a "SPA fallback" rewrite rule) — check `assets/` and the per-host notes below.

## Option B — SvelteKit + `@sveltejs/adapter-static`

Use when you want file-based routing (`src/routes/...`) and either full prerendering (every route becomes real, SEO-visible HTML at build time) or a single-page-app fallback shell.

```bash
npm install -D @sveltejs/adapter-static
```

```js
// svelte.config.js
import adapter from '@sveltejs/adapter-static';

export default {
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: undefined, // set to 'index.html' only for SPA mode — see below
      precompress: false,
      strict: true
    })
  }
};
```

### Full prerendering (preferred — better SEO, works without JS)

```js
// src/routes/+layout.js
export const prerender = true;
```

Leave `fallback` unset. Every route SvelteKit can statically render becomes its own `.html` file at build time. Two gotchas that account for most "my prerendered site is blank" reports:

1. **Don't set `export const ssr = false` on a page you also want prerendered.** `ssr = false` renders an empty shell — the prerendered file will exist but contain no real HTML, only a mount point. `ssr` and `prerender` are separate switches; for real prerendered content you need `ssr` to stay `true` (its default) and `prerender = true`.
2. **`trailingSlash`.** If the static host serves `/a.html` when a browser requests `/a` (most do, including GitHub Pages and Netlify), the default is fine. If your host requires an actual `/a/index.html` for a request to `/a/`, set `export const trailingSlash = 'always'` in the root layout so SvelteKit emits `a/index.html` instead of `a.html`.
3. Any route that isn't purely static-renderable at build time (reads `params` that aren't enumerable, depends on request headers/cookies, uses `+page.server.js`/`+server.js`) cannot be prerendered — those files are exactly what "static-only" rules out. If the user's app has any of these, flag it: either the data source needs to move to build-time (fetch at build, bake into the page) or the feature needs a different hosting model entirely (this skill doesn't cover that).

### SPA mode (fallback shell, client-side routing)

Only use this when SEO doesn't matter and there's no server-side logic in the app at all (no `+page.server.js`, `+layout.server.js`, `+server.js` anywhere — those require an actual server and are incompatible with a fallback-shell static export).

```js
// src/routes/+layout.js
export const ssr = false; // whole app renders client-side only
```
```js
// svelte.config.js
adapter({ fallback: 'index.html' })
```
You can still prerender specific pages (e.g. a marketing landing page) alongside an SPA-mode app: give that page's own `+page.js` `export const prerender = true; export const ssr = true;`, while the root layout keeps `ssr = false` for everything else. SvelteKit docs explicitly recommend prerendering as many routes as possible even in SPA mode — full client-only SPA is a "last resort" pattern because it's worse for SEO, worse for perceived performance, and breaks entirely if JS fails to load.

## Deployment notes by host

- **GitHub Pages**: serves from a repo/branch; needs `base` set in `svelte.config.js` (`kit: { paths: { base: '/repo-name' } }`) if not deploying to a custom domain or user/org root page. GitHub Pages needs a `.nojekyll` file in the output (Jekyll otherwise ignores `_`-prefixed files SvelteKit generates) and, for SPA-mode client routing, a `404.html` that's a copy of `index.html` (GitHub Pages' fallback mechanism).
- **Netlify**: drop a `_redirects` file (`/* /index.html 200`) in `static/` for SPA-mode fallback routing; use a `_headers` file for CSP/security headers (see `references/security.md`).
- **Cloudflare Pages**: same `_headers`/`_redirects` file convention as Netlify.
- **Vercel (static export)**: configure headers/rewrites via `vercel.json` instead of `_headers`/`_redirects`.
- **S3 + CloudFront**: set the S3 "error document" to `index.html` for SPA fallback (S3 static website hosting only, not the newer S3+CloudFront-only setups, which need a CloudFront function/Lambda@Edge for the rewrite); CSP has to be set via a CloudFront response-headers policy since there's no `_headers`-file equivalent.

Whichever host, confirm build output actually contains no reference to environment variables that were meant to stay server-side — see `references/security.md` for the `VITE_`/`PUBLIC_` prefix rule, since it's the most common way a static build accidentally ships a secret.
