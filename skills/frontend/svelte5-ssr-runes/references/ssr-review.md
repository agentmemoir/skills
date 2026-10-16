# Reviewing an Existing SSR App — Checklist

A build-focused skill needs a review counterpart: when the user asks to audit, debug, or review an existing SvelteKit/SSR app, walk this list and collect findings with file and line. Each item names the failure it catches, not just the rule.

## 1. Rendering modes

- Root `+layout.js` exports: is `ssr = false` set to dodge a bug? That turns the app into an SPA. Flag it and find the real cause.
- Per-route `ssr`/`csr`/`prerender` overrides: any `prerender = true` on a route whose content differs per user, or that has form actions? Both are hard errors waiting to happen.
- `csr = false` routes: do they still depend on JS (form enhancement, `{#await}` streaming, click handlers)? They will not work.

## 2. Server-invisible runes

- Effects populating rendered state: grep `.svelte` and `.svelte.ts` for `$effect` that assigns to `$state` used in markup. The server HTML will be empty and hydration pops the value in.
- `$derived` touching browser APIs: grep for `window.`, `document.`, `localStorage`, `matchMedia`, `navigator` inside `$derived` expressions and template expressions. These throw during SSR.
- Effects assumed to run server-side: analytics, SEO metadata, or data fetching inside `$effect` never execute during SSR.

## 3. Hydration hazards

- Nondeterministic render values: grep for `Date.now`, `new Date`, `Math.random`, `crypto.randomUUID`, `toLocaleString`, `toLocaleDateString`, `Intl.` without an explicit `timeZone`, and timestamp formatting in `.svelte` files.
- DOM ids from randomness or module counters; should be `$props.id()`.
- Browser-only reads in the render path (`typeof window` forks, `browser` from `$app/environment` used in markup).
- Invalid HTML nesting that browsers repair (`<div>` in `<p>`, block content in `<a>`), a common mismatch cause the dev server reports with component and line.
- Reproduce with the browser console open: `hydration_mismatch` is not suppressible and points at the offending HTML.

## 4. Request-scoped state

- Module-level `$state` or writable stores in `.svelte.js`/`.svelte.ts` files: is any of it per-user (identity, cart, tenant)? That leaks across requests in a long-lived server process.
- Stores written inside `load` functions: same leak, plus it breaks the "load is pure" rule.
- Context passed as a raw value instead of a getter: reactivity silently freezes; check `setContext` call sites for `() => value` or getters.
- Auth checks only in `+layout.server.js`: layout loads do not run on every client-side navigation and run concurrently with page loads. Confirm `hooks.server.js` also checks, or each protected page does.

## 5. Data and payload exposure

- What every `load` returns is serialized into the HTML. Inspect return objects for fields the browser should not see (password hashes, tokens, internal flags, other users' data), even if the template never renders them.
- Serialization violations in server `load`: functions, class instances, or custom prototypes. Should be devalue-compatible (`Date`, `Map`, `Set`, `BigInt`, `RegExp`, cycles).
- Streamed promises: missing rejection handling (attach `.catch()` or use SvelteKit `fetch`); `setHeaders`/`redirect` used after streaming has started.
- `event.fetch` vs global `fetch` inside `load`: global fetch loses cookie inheritance and response inlining.
- `data` copied into non-reactive locals or `onMount`: should be read reactively (`$derived`) so navigation updates reach the UI.

## 6. Secrets and security

Run the full `references/security.md` checklist; the review-specific greps:

- Private env imported into client-reachable modules: grep for `$env/static/private`, `$env/dynamic/private`, `process.env` in files outside `$lib/server`, `+*.server.js`, and hooks.
- `{@html}` with anything user- or API-derived; sanitization co-located with the render.
- `hooks.server.ts`: `handleError` returning raw error messages; missing security headers; CSP set in two places.
- Cookies: session cookies missing `httpOnly`/`secure`/`sameSite`; tokens in `load` payloads.
- Server-side `fetch` of user-supplied URLs (avatar import, link preview, webhook test): SSRF risk.

## 7. Failure drills

- Two-user test: log in as A and B in separate browsers and confirm no shared state bleeds through (poke the module-level state candidates from item 4).
- JS-disabled test: load key routes with JavaScript off; the content should still be the server-rendered version (not an empty shell).
- Slow-data test: throttle the network and confirm streamed `{#await}` blocks resolve, reject, and hydrate without mismatch.
- Navigation test: client-side navigate between parameterized routes and confirm data refreshes (a non-reactive `data` copy is the usual culprit).

## Output shape

Group findings by the sections above, each with file:line, the failure it causes in production, and the fix. Prefer a few high-confidence findings with reproductions over a long speculative list.
