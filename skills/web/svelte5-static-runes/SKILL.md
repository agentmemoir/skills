---
name: svelte5-static-runes
description: >-
  Build, migrate, or review static (no server) Svelte 5 apps using runes
  ($state, $derived, $effect, $props, $bindable) instead of legacy Svelte 4
  reactivity (export let, reactive dollar-colon statements, stores-as-default).
  Use whenever I mention Svelte 5, runes, a "static Svelte site",
  "Svelte SPA", "SvelteKit static site"/"adapter-static"/prerendered
  SvelteKit, deploying Svelte to GitHub Pages/Netlify/Cloudflare
  Pages/S3/any CDN, or converting Svelte 4 code (export let, on:click,
  writable stores) to Svelte 5. Also use when writing or reviewing .svelte
  files that must ship with no backend, to flag accidental server-only
  SvelteKit files (+page.server.js, +server.js, form actions) or exposed
  secrets, and to apply the bundled XSS/CSP/secrets security checklist.
  Trigger even for a bare pasted .svelte file or a vague "make this a
  static site" request.
---

# Svelte 5 Static-Only (Runes)

## What this skill covers

"Static-only" means the deliverable is a folder of pre-built HTML/CSS/JS with **no Node/edge server at request time** — it can be hosted on GitHub Pages, Netlify/Cloudflare/Vercel *static* hosting, S3+CloudFront, or opened as local files. That constraint rules out `+page.server.js`, `+server.js`, form actions, hooks.server.js, and any code path that assumes a running server. "Runes" means the component reactivity is written with Svelte 5's `$state`/`$derived`/`$effect`/`$props` primitives, not Svelte 4's `export let` / `$:` / implicit reactivity.

These two constraints interact: a static build only works cleanly if *no* code — including inside `$effect` — assumes it's running on a server per-request. Keep that in mind throughout; it's the source of most bugs when people move a SvelteKit app to `adapter-static`.

## Step 1 — Pick the right project shape

Ask (or infer from context) whether the app needs file-based routing, multiple prerendered pages, or SEO-friendly per-route HTML. This determines the whole setup, so don't skip it.

| Need | Use |
|---|---|
| Single page / dashboard / widget / embed, no routing | **Plain Vite + Svelte** (`npm create vite@latest -- --template svelte-ts`). Simplest possible static-only setup — there is no server to accidentally introduce. |
| Multiple routes, each prerendered to its own HTML file, SEO matters | **SvelteKit + `@sveltejs/adapter-static`** with `prerender = true`. |
| Multiple routes, but SEO doesn't matter (internal tool, Chrome extension, Electron/Tauri UI) | **SvelteKit + `adapter-static` in SPA mode** (a single `fallback: 'index.html'` shell, client-side routing). |

Default to plain Vite+Svelte unless I specifically need routing — it has less to misconfigure. Full setup steps, config files, and deployment notes for both paths are in `references/static-build.md`; read it before generating `svelte.config.js` / `vite.config.js` from memory, because prerender/adapter options change across Svelte versions and are easy to get subtly wrong (e.g. forgetting `trailingSlash`, or setting `ssr = false` on a page you also want prerendered, which produces an empty shell instead of real HTML).

## Step 2 — Write components with runes, not Svelte 4 syntax

Never write `export let`, `$:`, `on:click`, or a bare `writable()` store as the *primary* way to manage component state in new Svelte 5 code — these still compile in most configurations but they are legacy patterns being asked about here is runes specifically. The core mapping:

| Svelte 4 | Svelte 5 |
|---|---|
| `let count = 0` (reactive because top-level) | `let count = $state(0)` |
| `$: doubled = count * 2` | `let doubled = $derived(count * 2)` (or `$derived.by(() => ...)` for multi-statement logic) |
| `$: { sideEffect(count) }` | `$effect(() => { sideEffect(count) })` |
| `export let name` | `let { name } = $props()` |
| `export let value; bind:value` (child mutates) | `let { value = $bindable() } = $props()` |
| `onMount`/`onDestroy` for DOM-only setup/teardown | `$effect(() => { ...; return () => cleanup(); })` |
| `<slot name="header">` | `{#snippet header()}...{/snippet}` + `{@render header()}` |
| `writable()`/`readable()` store, `$store` in components | `$state(...)` in a `.svelte.js`/`.svelte.ts` module, imported directly (reactivity now works outside components) |

Read `references/runes.md` before writing non-trivial rune code — it covers the parts people reliably get wrong: `$derived` must stay pure (no side effects, no state mutation inside it), `$effect` must never write to the same state it reads (infinite loop), `$state.raw` for large/frozen data you reassign rather than mutate, `$effect.root`/`untrack` for state shared outside component lifecycles, and the exact class-based pattern for cross-component/module state. Getting these wrong produces bugs that only show up as odd re-render loops or stale UI, which are hard to diagnose after the fact — better to write it correctly the first time.

When migrating existing Svelte 4 code, `npx sv migrate svelte-5` handles the mechanical rewrite (this is the current tool; older docs may reference `svelte-migrate`), but always review the diff — automated migration doesn't reliably fix stores-as-cross-module-state patterns or effects that should have been derived values.

## Step 3 — Apply the security checklist

Static hosting doesn't mean "no security surface" — it removes server-side attack vectors but the client-side ones (XSS, secret leakage, unsafe third-party embeds) are entirely on you since there's no server-side layer to catch them. Before finishing any task that touches user-generated content, `{@html}`, environment variables, or third-party scripts, check `references/security.md`. The highest-impact rules, so they're not missed even on a quick task:

1. **Never pass unsanitized content to `{@html}`.** Svelte auto-escapes everything in `{expression}` braces, but `{@html ...}` bypasses that entirely — it is the single biggest XSS source in Svelte apps. Sanitize with DOMPurify (or a strict allowlist) immediately before rendering, not earlier in the pipeline where it might get bypassed by a later edit.
2. **Never put a real secret behind a `VITE_`-prefixed (or SvelteKit `PUBLIC_`-prefixed) env variable.** Vite inlines these into the shipped JS bundle at build time — anyone can read them from the built files. A static-only app has no server to hide a secret behind at all, so if the app needs a real API key, the key belongs on the third-party service's server or behind a separate serverless function/proxy I deploy elsewhere — flag this to me rather than quietly wiring the key into client code.
3. **Set a Content-Security-Policy even though there's no server to send headers from.** Static hosts still support this via a `<meta http-equiv="Content-Security-Policy">` tag in `app.html`/`index.html`, or via a host-specific headers file (Netlify `_headers`, Cloudflare Pages `_headers`, Vercel `vercel.json` headers) — see `references/security.md` for both.
4. **Treat every dynamic `href`/`src` as attacker-controlled if it can come from user input or an API response.** Svelte does not block `javascript:` URLs in `href` bindings — validate/allowlist the scheme yourself.
5. **Run `npm audit` (or equivalent) and pin lockfiles** before shipping — static sites still ship every dependency's code straight to the browser, so a compromised dependency is a direct client-side compromise.

## Reference files

- `references/runes.md` — full rune-by-rune guide with correct/incorrect patterns, class-based shared state, TypeScript typing for props/snippets, and the Svelte-4-to-5 migration table in detail.
- `references/static-build.md` — plain Vite+Svelte setup, SvelteKit+adapter-static setup (full-prerender and SPA-fallback modes), trailing-slash/base-path gotchas, and per-host deployment notes (GitHub Pages, Netlify, Cloudflare Pages, S3/CloudFront).
- `references/security.md` — full checklist: XSS/`{@html}`/DOMPurify, CSP for static hosts (meta tag + `_headers` templates), secrets/env vars, safe external links, dependency auditing, Trusted Types, localStorage/sessionStorage sensitivity, and a pre-ship checklist.
- `assets/` — copyable starter files: `vite.config.ts`, `svelte.config.js` (adapter-static), `_headers` (CSP template), and `SecureHtml.svelte` (a DOMPurify wrapper component).

Pull these in as needed rather than reproducing their contents from memory — the config option names and CSP directive specifics are exactly the kind of detail that goes stale or gets misremembered.
