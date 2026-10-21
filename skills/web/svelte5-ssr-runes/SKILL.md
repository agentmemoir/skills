---
name: svelte5-ssr-runes
description: >-
  Build, migrate, or review server-rendered Svelte 5 apps using runes
  ($state, $derived, $effect, $props, $bindable) with SvelteKit SSR
  (adapter-auto/node/cloudflare/vercel/netlify) or plain Vite SSR using
  svelte/server render() and hydrate(). Use whenever I mention Svelte 5
  SSR, server-side rendering, SvelteKit load functions, +page.server.js,
  +layout.server.js, hooks.server.js, form actions, streaming SSR, CSP nonces,
  hydration mismatches, or request-scoped state. Also use to review .svelte and
  server files for SSR-safety bugs: effects that never run on the server,
  module-level state leaking between users, non-deterministic render values,
  and secrets reaching the client. Trigger even on a bare pasted component that
  "renders differently on the server and client".
category: web
title: Svelte5 SSR runes
summary: >-
  Server-rendered Svelte 5 with runes, SvelteKit SSR, or plain Vite SSR. Build, migrate, or review
  apps that use runes: request-scoped state, hydration-safe rendering, streaming loads, CSP nonces,
  and an SSR security
  checklist.
say: >-
  "Build my Svelte 5 app with SSR and
  runes."
---

# Svelte 5 Server-Side Rendering (Runes)

## What this skill covers

"SSR" means every request is rendered to HTML by a server (Node, Bun, serverless, or edge) before the browser receives it; the same components then hydrate into an interactive app. Unlike a static-only build, a real server exists at request time, so `+page.server.js`, `+layout.server.js`, `+server.js`, form actions, and `hooks.server.js` are allowed — and are where data and secrets belong.

The runes part is what makes SSR tricky: every component runs twice, once on the server and once in the browser. Code that is fine in a client-only app breaks here:

- `$effect` never runs on the server, so any state it populates is missing from the server HTML.
- Module-level `$state` in `.svelte.ts` files is created once per server process and shared across all users' requests.
- Values computed from `Date.now()`, `Math.random()`, or `localStorage` during render differ between server and client, causing hydration mismatches.

Those three failures account for most SSR bugs in runes code, and each has a small correct pattern below.

## Step 1 — Pick the project shape

| Need | Use |
|---|---|
| Full app: routes, server data loading, forms, auth, streaming | **SvelteKit** with `adapter-auto` (Vercel/Netlify/Cloudflare auto-detect), `adapter-node` (self-host), or a platform adapter. This is the default; use it unless there is a reason not to. |
| A Svelte component tree inside an existing backend (Express/Hono/Fastify/Bun) | **Plain Vite + Svelte 5**: `render()` from `svelte/server` on the server, `hydrate()` in the browser. You own routing, headers, and request handling. |
| Mostly-static content with a few dynamic routes | SvelteKit with `export const prerender = true` per route (or `'auto'` to prerender popular pages and server-render the long tail). The dynamic routes still follow every rule here. |

Do not set `export const ssr = false` to "fix" an SSR bug — that turns the route into a client-rendered shell (an SPA), losing SEO and first paint. It is legitimate only for pages that genuinely cannot render without browser globals. `csr = false` is the opposite switch: server HTML with no hydration, for pages that need no interactivity.

Setup steps for both paths, plus adapters and page options, are in `references/ssr-build.md`. Read it before generating `svelte.config.js` / `vite.config.js`, because option names and adapter behavior differ across versions and are easy to get subtly wrong.

## Step 2 — Know which runes run on the server

This table is the core of the skill:

| Rune | During SSR | Notes |
|---|---|---|
| `$state(v)` | Runs | Initial value is rendered. Mutating it mid-render does not re-render already-emitted HTML — SSR is a single pass. |
| `$state.raw(v)` | Runs | No proxy. Good for large `data` payloads you replace wholesale instead of mutating. |
| `$derived(expr)` | Runs | Evaluated as part of rendering, so its output lands in the HTML. Keep it pure and free of browser-only APIs. |
| `$effect` / `$effect.pre` | **Never** | Browser-only. State it sets is absent from SSR HTML (pop-in after hydration). This is not a hydration error, but it is empty HTML and visible layout shift. |
| `$effect.root(fn)` | Never | Same. Do not build server-visible state inside it. |
| `$props()` / `$bindable()` | Runs | Load data arrives as props; initial values render. |
| `$props.id()` | Runs | SSR-safe unique ID, consistent between server and client (Svelte ≥ 5.20). Use it for `for`/`aria-labelledby` links. |
| `$inspect(v)` | Dev only | No SSR output. |
| `$state.snapshot(v)` | Runs | Use before handing state to a non-Svelte API or server library. |
| `$effect.tracking()` | `false` | The server compiler replaces it with the literal `false`; there is no tracking context during SSR. |

The classic SSR bug this table prevents:

```svelte
<!-- ❌ empty in the server HTML, then pops in after hydration -->
<script>
  let user = $state();
  $effect(() => { user = getUser(); });
</script>
<div>{user?.name}</div>
```

The fix is almost always the same: compute SSR-visible values in `$derived`, or fetch them in `load` and pass them as props. Keep `$effect` for things that only exist in the browser (canvas, observers, analytics, storage sync).

Read `references/runes-ssr.md` for the full rune-by-rune server behavior, hydration-safe value patterns, and the experimental async SSR status.

## Step 3 — Keep state per-request, never module-global

```ts
// ❌ one shared object for the whole server process — user A can see user B's data
// src/lib/user.svelte.ts
export const user = $state({ name: '' });
```

The canonical fix is to return per-request data from `load` and pass it down as props; when many nested components need it, put it in context with a getter:

```svelte
<!-- +layout.svelte -->
<script>
  import { setContext } from 'svelte';
  let { data } = $props();
  setContext('user', () => data.user);
</script>
```

```svelte
<!-- any child -->
<script>
  import { getContext } from 'svelte';
  const user = getContext('user');
</script>
<p>Hi {user().name}</p>
```

Context is attached to the component tree, and each SSR request gets its own tree, so it cannot leak between users. Pass a function (or object with getters) into `setContext`, not the value itself, or reactivity is lost. Per-request data that many server functions need can live on `event.locals`, populated in `hooks.server.ts`.

Module-level state is still fine for client-only app state that no user data touches (theme, feature flags), as long as nothing server-renders personalized values from it.

## Step 4 — Treat hydration as a contract

Hydration replays the server HTML; the client's first render must match it. Any value that differs causes a `hydration_mismatch`, which is deliberately not suppressible — fix the code, not the warning.

- Render deterministically: no `Date.now()`, no `new Date()` formatting, no `Math.random()`, no `crypto.randomUUID()`, no `localStorage`/`window`/`navigator` reads in the render path.
- Generate IDs with `$props.id()`, not randomness or module counters.
- Format dates on the server in `load` and pass strings, or always pass an explicit `timeZone` — server and client timezones differ.
- Client-only values (storage, media queries, geolocation): start from a server-safe default and fill in inside `$effect`/`onMount`, or gate markup on a `mounted` flag with a stable server fallback.

```svelte
<script>
  import { browser } from '$app/environment';

  let theme = $state('light');
  $effect(() => {
    if (!browser) return;
    theme = localStorage.getItem('theme') ?? 'light'; // after mount, so hydration matches
  });
</script>
```

In plain Svelte SSR (no SvelteKit), `$app/environment` is unavailable — use `typeof window !== 'undefined'` inside an effect, never in the render path.

## Step 5 — Load and stream data on the server

- `+page.server.ts` / `+layout.server.ts` for databases, files, and private env; universal `+page.ts` for public APIs that can run in either place.
- Server `load` must return data that survives devalue serialization: JSON plus `Date`, `Map`, `Set`, `BigInt`, `RegExp`, and cyclic references. No functions or class instances.
- Slow, non-essential data: return the promise and `{#await}` it in the page — nested promises stream as they resolve. Await essential data before returning so it is in the first paint.
- Use `event.fetch` inside `load`: it inherits request cookies and inlines responses for hydration instead of refetching.
- After navigation, `data` updates without recreating the component: derive from it (`$derived`) instead of copying it into non-reactive locals.

Async SSR (`await` in components) and remote functions are still experimental as of Svelte 5.57 / SvelteKit 2.7x (September 2026). Do not enable `compilerOptions.experimental.async` in production code unless I explicitly ask; the exact status and opt-in are in `references/runes-ssr.md`.

## Step 6 — Apply the SSR security rules

1. **Secrets stay private.** `$env/static/private` / `$env/dynamic/private` are server-only; only `PUBLIC_`-prefixed vars reach the browser. Imports from `$lib/server/` and `*.server.js` throw if a component pulls them in.
2. **Anything returned from `load` is embedded in the HTML payload** — all of it, not just the fields you render. Never return password hashes, tokens, or internal fields you do not need on the client.
3. **CSP with nonces.** Configure `kit.csp`; SvelteKit injects a nonce into its own inline scripts, and `%sveltekit.nonce%` covers manual tags in `app.html`. A real server can send real CSP headers — use that instead of a weaker `<meta>` tag.
4. **`{@html}` is still XSS.** Server-rendered does not mean sanitized. Sanitize untrusted HTML with DOMPurify immediately before render.
5. **Auth belongs in `hooks.server.ts`** (populate `locals`) plus route-level checks. Layout `load` functions do not run on every client-side navigation.
6. **CSRF protection is on by default** for form submissions; leave it on, and check origin yourself in any custom `+server.js` mutation endpoint.
7. **Session cookies:** `httpOnly`, `secure` in production, `sameSite: 'lax'` at minimum.
8. **Server-side `fetch` of user-supplied URLs is SSRF.** Allowlist hosts; block private IPs and cloud metadata endpoints.

Full checklist and code: `references/security.md`.

## Reviewing an existing app

When the task is auditing or debugging rather than building, work through `references/ssr-review.md`: rendering-mode checks, server-invisible runes, hydration hazards, request-scoped state, payload exposure, security greps, and failure drills. Report findings as file:line with the production failure each one causes.

## Reference files

- `references/runes-ssr.md` — rune-by-rune server behavior, hydration-safety patterns, request-scoped state, plain `svelte/server` render + `hydrate`, and the experimental async SSR / remote functions status.
- `references/ssr-build.md` — SvelteKit setup and adapters, page options (`ssr`/`csr`/`prerender`), hooks, form actions, streaming, plain Vite SSR, and deployment notes.
- `references/ssr-review.md` — audit checklist for existing SSR apps: rendering modes, server-invisible runes, hydration hazards, state scoping, payload exposure, security greps, and failure drills.
- `references/security.md` — secrets and env vars, CSP nonces, XSS, CSRF, auth/session handling, SSRF, error leakage, and a pre-ship checklist.
- `assets/` — copyable starter files: `svelte.config.js` (SvelteKit with CSP), `hooks.server.ts` (auth plus security headers), and `index.html` / `entry-server.js` / `entry-client.js` for plain Vite SSR (the trio is built in CI by `tests/plain-ssr`).
