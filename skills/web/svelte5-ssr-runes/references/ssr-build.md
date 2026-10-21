# SSR Builds for Svelte 5

Two supported shapes. Pick per the table in SKILL.md; details for each below.

## Option A — SvelteKit (default)

SvelteKit is the full-fledged SSR framework: file-based routing, server-side data loading, form actions, hooks, streaming, and adapters for every major host. Server rendering is the default behavior — there is no flag to turn it on.

```bash
npx sv create my-app     # current Svelte CLI; pick the SvelteKit template + TypeScript
cd my-app
npm install
npm run dev
```

Adapters decide the deployment target. Install one and reference it in `svelte.config.js`:

| Adapter | Target | Notes |
|---|---|---|
| `@sveltejs/adapter-auto` | Vercel, Netlify, Cloudflare, Azure, etc. | Default in new projects; detects the platform at build time. `npm run build` then deploy the platform's output. |
| `@sveltejs/adapter-node` | Your own Node server/container | Output is a standalone server: `node build`. Set `ORIGIN` when behind a proxy, `PORT`/`HOST` as needed. |
| `@sveltejs/adapter-cloudflare` | Cloudflare Pages/Workers | Workers runtime: no Node builtins, no filesystem, per-request CPU/memory limits. |
| `@sveltejs/adapter-vercel` / `@sveltejs/adapter-netlify` | That platform | Support per-route `config` (runtime, regions) via the `config` page option. |

If the whole app is static, `adapter-static` exists — but that is the static-site case covered by the sibling `svelte5-static-runes` skill, not this one.

### Page options that matter for SSR

Exported from `+page.js`, `+page.server.js`, `+layout.js`, or `+layout.server.js`. Child values override parent values, so a root layout can set site-wide defaults.

```js
export const prerender = true;      // build-time HTML; false = dynamic SSR (default); 'auto' = prerender if reachable, else server-render
export const ssr = true;            // default; false = empty shell rendered client-side only
export const csr = true;            // default; false = server HTML, zero JavaScript shipped
export const trailingSlash = 'never' | 'always' | 'ignore';
```

- `ssr = false` gives an SPA route. Use only for pages that cannot render on the server; it is not a fix for hydration bugs.
- `csr = false` is for content pages that need no hydration; forms cannot be progressively enhanced, links do full-page navigations, and HMR is off in dev (override with `export const csr = dev`).
- `prerender = true` is only safe if any two users hitting the route directly get the same content. Pages with form actions cannot be prerendered. Dynamic routes need an `entries()` function or crawlable links. `'auto'` covers the popular-pages-prerendered, long-tail-server-rendered case.
- If options are literal booleans or strings, SvelteKit evaluates them statically; otherwise it imports the module on the server to read them, so browser-only code must not run at module load.

### Data loading

- `+page.server.ts` / `+layout.server.ts`: runs only on the server, access to `cookies`, `locals`, `request`, databases, private env. Return value must be devalue-serializable.
- `+page.ts` / `+layout.ts` (universal): runs on the server during SSR and again in the browser during hydration (reusing `fetch` results); use for public APIs and for returning non-serializable values like component constructors.
- The component receives merged load data as `data`: `let { data } = $props()`. Types come from `./$types` (`PageProps`, `PageServerLoad`, ...).
- Layout and page loads run in parallel unless a child calls `await parent()`; watch for waterfalls when reordering.
- A load reruns when tracked `params`/`url` values change, when `depends(...)`-declared URLs are invalidated, or on `invalidateAll()`. Changes update the `data` prop without recreating the component, so derive from `data` instead of copying it into a one-time local.
- `error(status, message)` and `redirect(status, location)` throw; unexpected errors go through `handleError`.
- `setHeaders({...})` sets response headers from `load` (each header once; no `set-cookie`). A typical use is mirroring the upstream `cache-control` on the HTML response.

### Streaming

Returning a promise (nested in the load return object) streams that value to the browser after the initial HTML; render it with `{#await}`:

```js
// +page.server.js
export function load({ params }) {
  return {
    comments: loadComments(params.slug), // slow, non-essential → streamed
    post: await loadPost(params.slug)     // essential → blocks first paint
  };
}
```

- Only server `load` promises stream. A promise returned from a universal `load` is recreated in the browser instead.
- Once streaming starts you cannot `setHeaders` or `redirect`, and header/status changes after that point are errors.
- Platforms that buffer responses (AWS Lambda, Firebase) lose the progressive benefit; proxies such as NGINX need buffering disabled.
- Attach a `.catch(() => {})` to non-essential promises you do not fetch via SvelteKit's `fetch`, or a rejection before render can crash the server as an unhandled rejection. SvelteKit's `fetch` handles this.
- Streaming requires JavaScript for the `{#await}` block to resolve in the browser; server-rendered `csr = false` pages should not rely on it.

### Hooks (per-request server code)

`src/hooks.server.ts`:

- `handle({ event, resolve })` — runs on every request; the right place for auth/session lookup into `event.locals` and for response header tweaks before returning `resolve(event)`.
- `handleError({ error, status })` — maps unexpected errors to a client-safe value; never return stack traces or sensitive messages.
- `handleFetch` — adjusts `fetch` requests made in server `load`.

`event.locals` typing lives in `src/app.d.ts`:

```ts
declare global {
  namespace App {
    interface Locals { user: { id: string; name: string } | null }
  }
}
export {};
```

Auth implication: layout `load` functions do not run on every client-side navigation, and they run concurrently with page loads. Put the session check in `handle` (or in each protected `+page.server.js`) if it must run every time.

### Form actions and progressive enhancement

```js
// +page.server.js
export const actions = {
  default: async ({ request, cookies }) => {
    const data = await request.formData();
    if (!data.get('email')) return fail(400, { error: 'Email required' });
    // ... mutate, then redirect(303, '/thanks')
  }
};
```

```svelte
<form method="POST">
  <input name="email" />
  <button>Sign up</button>
</form>
```

Actions work without JavaScript, then `use:enhance` upgrades the same form to fetch-based submission with pending/error states. CSRF protection for form posts is on by default (production only). `GET` forms submit to the current URL as search params — a good home for SSR-relevant UI state (filters, sorting) because it appears in `page.url.searchParams` and in `load`.

### CSP and env configuration

Keep security config in `svelte.config.js` rather than hand-rolling headers:

```js
kit: {
  csp: {
    mode: 'auto', // nonces for dynamic pages, hashes for prerendered ones
    directives: { 'script-src': ['self'], /* ... */ }
  },
  env: { publicPrefix: 'PUBLIC_', privatePrefix: '' }
}
```

SvelteKit augments the directives with nonces (or hashes) for the inline scripts/styles it generates. Manual tags in `src/app.html` need `nonce="%sveltekit.nonce%"`. See `references/security.md` for the full setup and the `style-src 'unsafe-inline'` caveat with Svelte transitions.

### Deployment notes

- **Node/containers:** `adapter-node`, `node build`. Set `ORIGIN` to the public URL behind proxies so `url` and redirects are correct. Consider `BODY_SIZE_LIMIT` for uploads.
- **Edge/serverless:** no `fs` or Node builtins; use the platform's KV/storage and keep per-request work small. Check that your database driver has an edge-compatible mode.
- **Caching:** use `setHeaders` to set `cache-control`. Do not CDN-cache HTML that depends on cookies or the session unless you key the cache correctly (`Vary: Cookie`, or cache only anonymous responses). `prerender`/`'auto'` is the safe way to get CDN-cacheable pages.
- **Streaming platforms:** buffered runtimes lose streamed chunks; that is a performance trade-off, not a correctness bug.

## Option B — Plain Vite + Svelte SSR

Use when the backend already exists (Express, Hono, Fastify, Bun, Deno, a custom worker) and SvelteKit's routing does not fit. Svelte supplies `render()` from `svelte/server`; you supply everything else. Vite's official SSR guide (`vite.dev/guide/ssr`) documents this pattern in more depth.

```bash
npm create vite@latest my-app -- --template svelte-ts
cd my-app
npm install
```

Structure:

```
index.html          # template with <!--app-head--> / <!--app-html--> / __APP_PROPS__ placeholders
server.js           # your backend: imports the server entry, sends HTML
src/
  App.svelte
  entry-client.js   # hydrate(App, { target, props })
  entry-server.js   # export function renderPage(template, props) using render(App)
```

Copy `assets/index.html`, `assets/entry-server.js`, and `assets/entry-client.js` as the starting point — they form one working set, and the smoke test in `tests/plain-ssr` builds them on every CI run.

- Build: `vite build --outDir dist/client` then `vite build --ssr src/entry-server.js --outDir dist/server`. The first rewrites `dist/client/index.html` to link the hashed JS entry and CSS; the second emits ESM your backend imports.
- Production template: read `dist/client/index.html` and pass it to `renderPage()`. Do not hardcode `/src/entry-client.js` in a served template — that path only exists under the dev server, and a hand-written template also misses the CSS link the client build emits.
- Dev: run `vite dev` in middleware mode inside your backend. Read the root `index.html`, apply `vite.transformIndexHtml(url, html)`, load the server entry with `vite.ssrLoadModule('/src/entry-server.js')`, then call `renderPage(template, props)`.
- There is no `$app/*`: use `typeof window !== 'undefined'` for environment checks, and avoid importing any `$app/environment` helpers.
- Props cross the wire in a `<script type="application/json">` tag; `renderPage` JSON-escapes `<` so a prop containing `</script>` cannot break out. `devalue` is the alternative for richer values.
- Hydrate with `hydrate()`, not `mount()`, and if you render multiple Svelte roots on one page pass a distinct `idPrefix` to each `render()` call.
- You own security: CSP headers, cookies, CSRF, and body parsing are all your backend's job. Apply the same rules from `references/security.md`.

## SvelteKit 3 status (September 2026)

SvelteKit 3 is in release candidate; the stable line is 2.7x. Everything in this skill targets stable Svelte 5 + SvelteKit 2. Known direction changes worth knowing before a migration: a task-based `sveltekit-3` migration in `sv`, `#lib` subpath imports replacing `$lib` in newly created projects, and flattened config. Check `next.svelte.dev/docs/kit/migrating-to-sveltekit-3` rather than guessing when a migration comes up.
