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
  writable stores) to Svelte 5. Also use when UI state lives in the URL
  (tabs, filters, search params, query string) or I mention shallow routing
  or page.url going stale.
  Also use when writing or reviewing .svelte files that must ship with no
  backend, to flag accidental server-only SvelteKit files
  (+page.server.js, +server.js, form actions) or exposed secrets, and to
  apply the bundled XSS/CSP/secrets security checklist. Trigger even for a
  bare pasted .svelte file or a vague "make this a static site" request.
category: web
title: Svelte5 static runes
summary: >-
  Static (no server) Svelte 5 apps with runes and adapter-static. Build, migrate, or review apps that
  use runes instead of legacy Svelte 4 reactivity, with SvelteKit 3 adapter-static setup, URL/tab
  state in the query string, and an XSS/CSP/secrets security
  checklist.
say: >-
  "Build my Svelte 5 static site with
  runes."
---

# Svelte 5 Static-Only (Runes)

## What this skill covers

"Static-only" means the deliverable is a folder of pre-built HTML/CSS/JS with **no Node/edge server at request time** — it can be hosted on GitHub Pages, Netlify/Cloudflare/Vercel *static* hosting, S3+CloudFront, or opened as local files. That constraint rules out `+page.server.js`, `+server.js`, form actions, hooks.server.js, and any code path that assumes a running server. "Runes" means the component reactivity is written with Svelte 5's `$state`/`$derived`/`$effect`/`$props` primitives, not Svelte 4's `export let` / `$:` / implicit reactivity.

These two constraints interact: a static build only works cleanly if *no* code — including inside `$effect` — assumes it's running on a server per-request. Keep that in mind throughout; it's the source of most bugs when people move a SvelteKit app to `adapter-static`.

Targets SvelteKit 3.x (currently 3.2) and Svelte 5.x. Where SvelteKit 2.x differs, the 2.x form is given in parentheses; do not mix the two in one codebase.

When you write, migrate, or change code, load the `debloat` skill first. This skill fixes what the app must do; debloat caps how much code you may add to do it.

## Process

- [ ] 1. Pick the project shape (Step 1). Note whether routing exists at all.
- [ ] 2. Write components with runes, not Svelte 4 syntax (Step 2). Read `references/runes.md` before writing any rune that lives outside a component, and before writing a `$derived` or `$effect` that touches more than one value.
- [ ] 3. If the app has tabs, filters, sort, pagination, or any view that a shareable link should restore, read `references/url-state.md` and put that state in the URL (Step 3). Do not skip this because the change "looks small" — a single `$derived` over `page.url` is enough to get it wrong.
- [ ] 4. Apply the security checklist (Step 4) to anything touching `{@html}`, env vars, external URLs, or third-party scripts.
- [ ] 5. Run the "Checklist before saying done" at the bottom from the diff, and report the answer. Do not claim completion without it.

## Step 1 — Pick the right project shape

Ask (or infer from context) whether the app needs file-based routing, multiple prerendered pages, or SEO-friendly per-route HTML. This determines the whole setup, so don't skip it.

| Need | Use |
|---|---|
| Single page / dashboard / widget / embed, no routing | **Plain Vite + Svelte** (`npm create vite@latest -- --template svelte-ts`). Simplest possible static-only setup — there is no server to accidentally introduce. |
| Multiple routes, each prerendered to its own HTML file, SEO matters | **SvelteKit + `@sveltejs/adapter-static`** with `prerender = true`. |
| Multiple routes, but SEO doesn't matter (internal tool, Chrome extension, Electron/Tauri UI) | **SvelteKit + `adapter-static` in SPA mode** (a single `fallback: 'index.html'` shell, client-side routing). |

Default to plain Vite+Svelte unless I specifically need routing — it has less to misconfigure. Full setup steps, config files, and deployment notes for both paths are in [references/static-build.md](references/static-build.md); read it before writing `vite.config.js` (SvelteKit 3) or `svelte.config.js` (2.x) from memory, because the config location changed in 3.0 and the prerender/adapter options are easy to get subtly wrong (e.g. forgetting `trailingSlash`, or setting `ssr = false` on a page you also want prerendered, which produces an empty shell instead of real HTML).

## Step 2 — Write components with runes, not Svelte 4 syntax

Never write `export let`, `$:`, `on:click`, or a bare `writable()` store as the *primary* way to manage component state in new Svelte 5 code. They still compile in most configurations, but they are legacy patterns, and runes are the subject of this skill. The core mapping:

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

Read [references/runes.md](references/runes.md) before writing rune code that spans files or mixes reads and writes — it covers the parts people reliably get wrong: `$derived` must stay pure (no side effects, no state mutation inside it), `$effect` must never write to the same state it reads (infinite loop), `$state.raw` for large/frozen data you reassign rather than mutate, `$effect.root`/`untrack` for state shared outside component lifecycles, and the exact class-based pattern for cross-component/module state. These mistakes surface as re-render loops or stale UI, which are hard to diagnose after the fact.

Two rules from that file matter often enough to repeat, because agents skip the read and break them:

- Runes outside a component file require a compiled-by-Svelte extension: `.svelte.js` or `.svelte.ts`. A plain `.js`/`.ts` module leaves `$state` undefined at runtime.
- Module-level `$state` is safe in a static SPA, where one browser session owns one module instance. It is not safe on a server: a prerendered page still evaluates that module during the build, and an SSR app shares it across every user's request. If the same code must run under SSR, follow `svelte5-ssr-runes` instead.

When migrating existing Svelte 4 code, `npx sv migrate svelte-5` handles the mechanical rewrite (this is the current tool; older docs may reference `svelte-migrate`), but always review the diff — automated migration doesn't reliably fix stores-as-cross-module-state patterns or effects that should have been derived values.

## Step 3 — Put URL state in the URL

Tabs, filters, sort order, and pagination are URL state, not component state. Get this wrong and the app renders the old tab after the address bar changed, or a shared link opens the wrong view. Read [references/url-state.md](references/url-state.md) before writing any code that reads `page.url`, calls `goto`/`replaceState`, or derives UI from a query param. The rules that cause the bug, so they are not missed on a quick task:

1. **Derive from the URL with `$derived`.** `const tab = $derived(page.url.searchParams.get('tab') ?? 'overview')`. Never copy the URL into `$state` once at init — that value never updates on back/forward.
2. **Know what `page.url` means.** It describes the *rendered* page. After a shallow write it is stale by design: 3.x puts the target in `page.shallow.url`; 2.x puts it in `page.state`. Read `page.shallow?.url ?? page.url` (3.x) when you need the visible URL.
3. **Build each new URL from the freshest base.** Copy `visibleUrl()` from the reference module and set params on it. A base taken from a stale `page.url` silently drops params written earlier.
4. **Do not add a revision counter to fix staleness.** Re-running a reader of a stale `page.url` returns the same old value. Counters only help for state you own.
5. **Write the URL in the event handler, never in an `$effect`.** An effect that writes the URL re-runs on its own change: loops, duplicate history entries, work after paint.
6. **Prefer a real navigation for UI that must react now.** `goto(url, { replace: true, reset: false })` in 3.x (`{ replaceState: true, noScroll: true, keepFocus: true }` in 2.x). Use `goto(url, { shallow: true })` (3.x) or `replaceState(url, state)` (2.x) only when the page must stay rendered and you accept that `page.url` still describes it.
7. **Keep one canonical URL.** Delete params that hold their default, and use replace rather than push so the back button does not collect duplicate views.

## Step 4 — Apply the security checklist

Static hosting doesn't mean "no security surface" — it removes server-side attack vectors but the client-side ones (XSS, secret leakage, unsafe third-party embeds) are entirely on you since there's no server-side layer to catch them. Before finishing any task that touches user-generated content, `{@html}`, environment variables, or third-party scripts, check [references/security.md](references/security.md). The highest-impact rules, so they're not missed even on a quick task:

1. **Never pass unsanitized content to `{@html}`.** Svelte auto-escapes everything in `{expression}` braces, but `{@html ...}` bypasses that entirely — it is the single biggest XSS source in Svelte apps. Sanitize with DOMPurify (or a strict allowlist) immediately before rendering, not earlier in the pipeline where it might get bypassed by a later edit.
2. **Never put a real secret behind a `VITE_`-prefixed (or SvelteKit `PUBLIC_`-prefixed) env variable.** Vite inlines these into the shipped JS bundle at build time — anyone can read them from the built files. A static-only app has no server to hide a secret behind at all, so if the app needs a real API key, the key belongs on the third-party service's server or behind a separate serverless function/proxy I deploy elsewhere — flag this to me rather than quietly wiring the key into client code.
3. **Set a Content-Security-Policy even though there's no server to send headers from.** Static hosts still support this via a `<meta http-equiv="Content-Security-Policy">` tag in `app.html`/`index.html`, or via a host-specific headers file (Netlify `_headers`, Cloudflare Pages `_headers`, Vercel `vercel.json` headers) — see [references/security.md](references/security.md) for both.
4. **Treat every dynamic `href`/`src` as attacker-controlled if it can come from user input or an API response.** Svelte does not block `javascript:` URLs in `href` bindings — validate/allowlist the scheme yourself.
5. **Run `npm audit` (or equivalent) and pin lockfiles** before shipping — static sites still ship every dependency's code straight to the browser, so a compromised dependency is a direct client-side compromise.

## Checklist before saying done

Answer these from the diff. A blank or inferred answer means the work is not done yet.

1. Which single module owns URL reads and writes? Name the file. Two components building query strings is the defect, not a style issue.
2. What does the tab/filter UI derive from, and what does it show after a shallow write has already happened?
3. Does any one-time `$state` initialiser copy a value out of `page.url` or `location`? Rewrite it as `$derived`.
4. Does any `$effect` write to the URL, or to state it also reads? Move the write into the event handler.
5. Was `grep -rn "history\.\|page\.url\|location\.href" src` run, and is every hit accounted for?
6. Does the repo contain `+page.server.js`, `+server.js`, `hooks.server.js`, or a `VITE_`/`PUBLIC_` variable holding a real secret? Either one ends the static-only claim.
7. Does the build output open with a clean console, and does a reload on a deep link such as `/?tab=settings` restore that tab?

## Reference files

- [references/runes.md](references/runes.md) — full rune-by-rune guide with correct/incorrect patterns, class-based shared state, TypeScript typing for props/snippets, and the Svelte-4-to-5 migration table in detail.
- [references/url-state.md](references/url-state.md) — URL as UI state: deriving tabs and filters, what `page.url` means after a shallow write, the 3.x/2.x `goto` options, one URL module, canonical defaults, the grep audit, and the plain-Vite equivalent.
- [references/static-build.md](references/static-build.md) — plain Vite+Svelte setup, SvelteKit+adapter-static setup (full-prerender and SPA-fallback modes), SvelteKit 3 config in `vite.config.js`, trailing-slash/base-path gotchas, and per-host deployment notes (GitHub Pages, Netlify, Cloudflare Pages, S3/CloudFront).
- [references/security.md](references/security.md) — full checklist: XSS/`{@html}`/DOMPurify, CSP for static hosts (meta tag + `_headers` templates), secrets/env vars, safe external links, dependency auditing, Trusted Types, localStorage/sessionStorage sensitivity, and a pre-ship checklist.
- [assets/](assets/) — copyable starter files: `vite.config.ts` (plain Vite), `vite.config.sveltekit.ts` (SvelteKit 3 + adapter-static), `_headers` (CSP template), and `SecureHtml.svelte` (a DOMPurify wrapper component).

Read the matching reference before writing code in its area, and never reproduce config options or CSP directives from memory — they are exactly the details that go stale or get misremembered. If a reference contradicts this file, the reference wins and this file is the bug: say so.
