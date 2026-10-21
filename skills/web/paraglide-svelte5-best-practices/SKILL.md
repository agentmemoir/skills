---
name: paraglide-svelte5-best-practices
description: >-
  Expert guidance for building type-safe, performant i18n apps with Paraglide JS 2.x
  (compiler-based, tree-shakable) and Svelte 5 (runes). Covers setup, message
  authoring, locale strategies, i18n routing, SSR/SSG, rich-text markup with
  Svelte 5 snippets, reactivity patterns, testing, and troubleshooting. Use when
  I mention Paraglide, inlang, paraglide-js, SvelteKit i18n, locale
  switching, localized URLs, or Svelte 5 runes in an internationalization context.
category: web
title: Paraglide Svelte5 best practices
summary: >-
  Type-safe, tree-shakable i18n for Svelte 5 and SvelteKit with Paraglide JS 2.x. Covers
  compiler-based messages, locale strategies, localized URLs, SSR/SSG setup, rich-text markup with
  Svelte 5 snippets, testing, and common
  pitfalls.
say: >-
  "Set up Paraglide i18n in my SvelteKit app with localized
  URLs."
version: 1.0.0
last_verified: 2026-09-11
---

# Paraglide JS + Svelte 5 Best Practices

**Treat locale as request/build state resolved by a compiler, not as reactive app state — let Paraglide's full-document navigation handle locale switches, and let Svelte 5 runes own everything else.** Paraglide JS is SvelteKit's official i18n integration: it compiles `messages/{locale}.json` into tree-shakable, fully typed ESM functions, giving up to ~70% smaller i18n bundles than runtime libraries (≈47 KB vs ≈205 KB in the published benchmark with 5 locales / 200 messages), with no async waterfalls and no i18n provider to wire into Svelte 5 components.

---

## 1. Quick-Reference Decision Table

| Decision | Recommended default | Why |
|---|---|---|
| Install path | `npx sv add paraglide="languageTags:en,de"` on a new SvelteKit app | Scaffolds Vite plugin, hooks, `app.html` attrs, `.gitignore` in one step |
| Package | `@inlang/paraglide-js` v2.x | v1 adapter `@inlang/paraglide-js-adapter-sveltekit` is deprecated — use the core package directly |
| Strategy (SSR + localized URLs) | `["url", "cookie", "baseLocale"]` | URL is SEO source of truth; cookie persists user choice server-visibly; `baseLocale` always resolves last |
| Strategy (add stored override) | `["localStorage", "cookie", "preferredLanguage", "url", "baseLocale"]` | `localStorage` alone is invisible to the first SSR request; cookie bridges server/client |
| Locale switch behavior | Default `setLocale(locale)` (full document navigation) | Framework reactivity does **not** re-render `<html lang>`, `dir`, `<title>`, or localized URLs; navigation does |
| AsyncLocalStorage | Keep enabled (default) | Vercel Edge and Cloudflare Workers (Node compat) support it; disabling risks leaking locale between concurrent requests |
| TS declarations | `emitTsDeclarations: true` (TypeScript ≥ 5.6) | Keeps Svelte + TS language servers in sync when keys change during dev |
| Message keys | Flat, stable, human-readable random keys (`calm_green_otter`) | Official recommendation; nested keys work but flat keys are preferred |
| Prerendering | `export const prerender = true` + `entries()` per locale | SSG needs every locale to resolve to a distinct URL file |
| Reactivity for locale | None in components by default | `getLocale()` is request-scoped; a new document is rendered per locale, so runes don't need to track it |

---

## 2. Setup & Configuration (Paraglide 2.x + SvelteKit + Svelte 5)

### 2.1 Fastest path

```bash
npx sv create my-app
npx sv add paraglide="languageTags:en,de,demo:yes"
```

The Svelte CLI add-on configures the inlang project, the Vite plugin, SvelteKit `handle`/`reroute` hooks, `%lang%`/`%dir%` in `app.html`, and an optional demo page.

### 2.2 Manual setup (full boilerplate)

Install and scaffold the project, then wire four files:

**`vite.config.ts`** — plugin with explicit strategy:

```ts
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { paraglideVitePlugin } from '@inlang/paraglide-js';

export default defineConfig({
  plugins: [
    sveltekit(),
    paraglideVitePlugin({
      project: './project.inlang',
      outdir: './src/lib/paraglide',
      emitTsDeclarations: true,
      strategy: ['url', 'cookie', 'baseLocale'],
    }),
  ],
});
```

`emitTsDeclarations: true` regenerates `.d.ts` as you edit messages so the Svelte and TypeScript servers stay in sync; it requires TypeScript 5.6+ (set `false` for the faster JSDoc-inference path).

**`src/app.html`** — replace the hard-coded lang:

```html
<!doctype html>
<html lang="%lang%" dir="%dir%">
```

**`src/hooks.server.ts`** — server middleware with request-scoped locale:

```ts
import type { Handle } from '@sveltejs/kit';
import { paraglideMiddleware } from '$lib/paraglide/server';
import { getTextDirection } from '$lib/paraglide/runtime';

const paraglideHandle: Handle = ({ event, resolve }) =>
  paraglideMiddleware(event.request, ({ request: localizedRequest, locale }) => {
    event.request = localizedRequest;
    return resolve(event, {
      transformPageChunk: ({ html }) =>
        html.replace('%lang%', locale).replace('%dir%', getTextDirection(locale)),
    });
  });

export const handle: Handle = paraglideHandle;
```

The middleware detects the locale (strategies in order), redirects document requests when the URL disagrees with the detected locale, delocalizes `/de/about → /about` before SvelteKit sees it, and wraps the request in `AsyncLocalStorage` so `getLocale()` returns the right locale per concurrent request.

**`src/hooks.ts`** — routing boundary (must be `hooks.ts`, **not** `hooks.server.ts`):

```ts
import type { Reroute } from '@sveltejs/kit';
import { deLocalizeUrl } from '$lib/paraglide/runtime';

export const reroute: Reroute = (request) => deLocalizeUrl(request.url).pathname;
```

<details>
<summary><strong>Centralized compiler config (optional, recommended for monorepos)</strong></summary>

```ts
// project.inlang/paraglide.config.ts
import { defineConfig } from '@inlang/paraglide-js';

export default defineConfig({
  outdir: './src/lib/paraglide',
  strategy: ['url', 'cookie', 'baseLocale'],
  urlPatterns: [
    { pattern: '/', localized: [['en', '/']] },
    {
      pattern: '/:path(.*)?',
      localized: [
        ['en', '/en/:path(.*)?'],
        ['de', '/de/:path(.*)?'],
      ],
    },
  ],
});
```

Precedence: CLI flags / plugin options > config file > built-in defaults. Watch mode hot-reloads the config.
</details>

---

## 3. Core Usage Patterns (Messages, Locale, Routing)

### 3.1 Messages

```ts
import { m } from '$lib/paraglide/messages';
import type { LocalizedString } from '$lib/paraglide/runtime';

m.hello_world();                       // "Hello World!"
m.greeting({ name: 'Ada' });           // "Hello Ada!" — params are typed
m.greeting({ name: 'Ada' }, { locale: 'de' }); // force locale for one call
const title: LocalizedString = m.welcome_title(); // brand-safe string type
```

Messages live in `messages/{locale}.json`; locales are declared in `project.inlang/settings.json` (`baseLocale` + `locales`). Prefer flat stable keys; nested keys are supported via `m['user.profile.title']()`. Dynamic key access defeats tree-shaking — map dynamic IDs to explicit message references instead.

### 3.2 Getting and setting the locale

```ts
import { getLocale, locales, setLocale, getTextDirection } from '$lib/paraglide/runtime';

getLocale();          // e.g. "de" — request-scoped on the server
getTextDirection();   // "ltr" | "rtl" for current locale
setLocale('de');      // full document navigation to the localized URL
```

`setLocale()` updates your configured strategies and then performs a **full document navigation** — to the localized URL when the `url` strategy is active, otherwise a reload. This is intentional: `<html lang>`, `dir`, `<title>`, metadata, and the localized URL are document-level state that framework reactivity cannot update.

The `setLocale(locale, { reload: false })` escape hatch exists only for fully client-rendered surfaces (embedded widgets, extension pages) that must preserve non-restorable in-memory state. Never use it for ordinary locale pickers, on SSR/SSG documents, or on routes whose strategy includes `url` — it leaves the old URL and shell in place so `getLocale()` keeps resolving the old locale.

### 3.3 Localized URLs and links

```ts
import { localizeHref, deLocalizeUrl, localizeUrl } from '$lib/paraglide/runtime';

localizeHref('/blog');                          // "/de/blog" for current locale
localizeHref('/blog', { locale: 'de' });        // explicit
localizeUrl('https://example.com/about', { locale: 'de' }).href; // full URL form
```

URL patterns use the standard `URLPattern` syntax; **order matters** — put specific patterns before wildcards, and test them at urlpattern.com.

### 3.4 Svelte 5 locale switcher (idiomatic)

```svelte
<script lang="ts">
  import { page } from '$app/state';                       // Svelte 5: object, not a store
  import { resolve } from '$app/paths';
  import { locales, localizeHref } from '$lib/paraglide/runtime';
</script>

<nav aria-label="Languages">
  {#each locales as locale (locale)}
    <a
      href={resolve(localizeHref(page.url.pathname, { locale }))}
      data-sveltekit-reload
      aria-current={page.params.locale === locale ? 'page' : undefined}
    >
      {locale}
    </a>
  {/each}
</nav>
```

Two Svelte 5 details matter here: `$app/state` exposes `page` as a reactive object (the `$page` store and `$app/stores` are the legacy pattern), and `data-sveltekit-reload` on cross-locale links keeps the localized URL, server-rendered document, and runtime locale in sync — required for prerendered crawling too.

---

## 4. Rich Text with Svelte 5 Snippets (`ParaglideMessage`)

Markup lets translators control structure while your app controls rendering. Tag names are app-defined — nothing maps to HTML automatically.

```json
// messages/en.json
{
  "cta": "{#link to=|/docs|}Read the docs{/link}",
  "welcome": "{#b}Hi {name}{/b}{#icon/}"
}
```

```svelte
<script lang="ts">
  import { ParaglideMessage } from '@inlang/paraglide-js-svelte';
  import { m } from '$lib/paraglide/messages';
  const name = $props().name; // or any $state
</script>

<ParaglideMessage message={m.welcome} inputs={{ name }}>
  {#snippet b({ children })}
    <strong>{@render children?.()}</strong>
  {/snippet}
  {#snippet icon({ attributes })}
    <Icon variant={attributes?.variant} />
  {/snippet}
</ParaglideMessage>
```

`<ParaglideMessage>` uses `message.parts()` when markup exists and falls back to `message()` for plain text; the `{#snippet tag({ children, options, attributes })}` syntax is exactly the Svelte 5 snippet pattern — no slots, no `<slot>` legacy. Note the literal-syntax `to=|/docs|` (pipe-delimited) and that `m.welcome()` alone returns markup-stripped plain text.

---

## 5. Svelte 5 Runes Integration: What's Reactive (and What Isn't)

The key mental model: **Paraglide owns locale as document/request state; Svelte 5 runes own UI state.** Because locale changes ship a new document, you rarely need runes to track `getLocale()`. Patterns that come up in practice:

**Locale-dependent derived values inside a single document** (e.g., a client-only surface using `reload: false`, or a preview pane rendering multiple locales explicitly):

```svelte
<script lang="ts">
  import { getLocale, locales } from '$lib/paraglide/runtime';
  import { m } from '$lib/paraglide/messages';

  let { locale = getLocale() } = $props();          // typed props
  // $derived re-evaluates when `locale` prop changes — not when
  // Paraglide's internal locale changes (it doesn't, without navigation):
  const greeting = $derived(m.greeting({ name: 'Ada' }, { locale }));
  const isRtl = $derived(getTextDirection(locale) === 'rtl');
</script>
```

**Passing the forced locale down instead of reading global state** is the runes-friendly pattern: `{ locale }` options on each message call make components pure functions of props, which is exactly how Svelte 5 wants state to flow. Reserve `$effect` for true side effects (e.g., persisting a preview locale) — never assign to a `$derived`, and don't write `$state` from inside `$effect` to "push" locale around; pass props instead.

**Global client state (e.g., "last previewed locale" for an in-app translator tool):**

```ts
// src/lib/locale-preview.svelte.ts — .svelte.ts files support runes at module scope
export const preview = $state({ locale: 'en' as string | undefined });
```

Module-level `$state` in `.svelte.ts` files is shared across all importers — fine for app-wide singletons, but remember it is *not* how production locale works (that's the strategy chain + document navigation).

---

## 6. SSR, Hydration, and SSG

### 6.1 SSR rules

- One `handle` chain order: put `paraglideHandle` first (or before auth handlers that need `event.locals` keyed by locale) so downstream hooks see the delocalized request.
- Behind a TLS-terminating proxy, pass `effectiveRequestUrl` so URL matching and redirects use the browser-facing origin.
- Keep `AsyncLocalStorage` on; it is what makes `getLocale()` safe under concurrent requests and streaming SSR. The `disableAsyncLocalStorage` fallback is only for runtimes without `node:async_hooks` **and** guaranteed per-request isolation — using it elsewhere can leak locale across users.

### 6.2 Hydration correctness

Server and client must resolve the locale from the same strategy order. The classic mismatch: server resolves from URL but the client strategy reads `localStorage` first, which doesn't exist at SSR time. Fix by including a server-visible `cookie` strategy when a persisted choice must shape the first response.

### 6.3 SSG (adapter-static / prerender)

Prerendering never runs the middleware — set the locale per page during the build:

```ts
// src/routes/[locale]/+layout.ts
import { setLocale, assertIsLocale } from '$lib/paraglide/runtime';
import type { LayoutLoad } from './$types';

export const prerender = true;
export function load({ params }: { params: { locale: string } }) {
  setLocale(assertIsLocale(params.locale));
}
```

```ts
// src/routes/[locale]/+page.ts
import { locales } from '$lib/paraglide/runtime';
export const prerender = true;
export function entries() {
  return locales.map((locale) => ({ locale }));
}
```

SSG requires **every** locale to carry a URL prefix (configure `urlPatterns` so `/en/…` and `/de/…` both exist), otherwise SvelteKit can't emit distinct files per locale. For the static adapter's SPA fallback, set `kit.paths.relative = false` to avoid locale-prefixed asset 404s, and use `generateStaticLocalizedUrls()` for sitemaps.

---

## 7. Performance & Tree-Shaking

- **Call message functions directly.** `m.hello()` compiles to one small ESM function; your bundler drops unused messages and their translations automatically. Bundle size stays flat as the catalog grows (benchmark: 47 KB whether the project holds 200 or 1,000 messages, vs i18next growing 205 → 414 KB).
- **Avoid runtime-built key strings.** `` m[`${key}`]() `` and object-spread catalogs of *all* of `m` defeat tree-shaking. For dynamic menus, map CMS/content IDs to explicit message functions, or have the CMS return already-localized content.
- **`emitTsDeclarations` has a dev cost.** It's the right call for correctness during active development; on very large catalogs, teams have reported slower dev-server iteration on Paraglide 2.x — if dev feels sluggish, profile before assuming the compiler is the cause; production builds are unaffected.
- **Scope `LocalizedString` in your API surface** so untranslated strings fail type-checking at component boundaries, not in production.

---

## 8. Testing (Vitest)

Compile against a test-friendly strategy and pin the locale explicitly per test — the `globalVariable` strategy exists precisely for non-user-facing contexts like tests and scripts:

```ts
// vite.config.ts (test block) — compile with globalVariable for unit tests
paraglideVitePlugin({
  project: './project.inlang',
  outdir: './src/lib/paraglide',
  strategy: ['globalVariable', 'baseLocale'],
  emitTsDeclarations: true,
}),
```

```ts
// src/lib/i18n-test.ts
import { setLocale } from '$lib/paraglide/runtime';

export function withLocale<T>(locale: string, fn: () => T): T {
  setLocale(locale as never, { reload: false }); // test-only; no document
  const result = fn();
  return result;
}
```

For tests that call messages on the server outside a request context (pure functions, Zod schemas), this avoids the "no locale in this context" failure entirely — or bypass i18n by asserting against the base locale output. Component tests with `@testing-library/svelte` can pass `{ locale }` options explicitly rather than relying on any global, which keeps components deterministic.

---

## 9. Common Pitfalls & Fixes

| Symptom | Cause | Fix |
|---|---|---|
| `setLocale()` changed messages but `<html lang>`/`dir`/URL didn't update | Locale switching is document navigation; `reload: false` skips all document updates | Use default `setLocale(locale)`; reserve `reload: false` for client-only surfaces |
| Hydration mismatch / wrong locale flash on first paint | Server and client strategy order differ, or client relies on `localStorage` which SSR can't read | Align strategy arrays; add `cookie` for server-visible persistence |
| "No locale" or wrong locale when calling `m.*()` in plain server modules | Called outside request context (no URL/AsyncLocalStorage available) | Call messages inside `load`/hooks/actions, or pass `{ locale }` explicitly, or compile with `globalVariable` for non-user surfaces |
| Localized URLs 404 assets under adapter-static SPA fallback | Relative asset paths resolve under the locale prefix | Set `kit.paths.relative = false` |
| Prerender only generates base-locale pages | No `entries()` enumerating locales; or base locale unprefixed in `urlPatterns` | Export `entries()` from `+page.ts` mapping `locales`; prefix all locales for SSG |
| ESLint `no-navigation-without-resolve` flags `localizeHref` links | SvelteKit rule can't see through Paraglide's href helper | Use `resolve(localizeHref(...))` or scope the rule for Paraglide-wrapped hrefs |
| URL and locale drift apart after client-side navigation | URL strategy set, but client nav didn't re-sync document | Add `data-sveltekit-reload` to cross-locale links; optionally re-sync in root `+layout.svelte` — this doesn't replace server middleware |
| Sitemap/crawler misses locale variants | SvelteKit crawls anchors only | Render `localizeHref` anchor tags for every locale, or use `generateStaticLocalizedUrls()` |
| Old `@inlang/paraglide-js-adapter-sveltekit` import errors | Package deprecated in favor of core v2 | Migrate to `@inlang/paraglide-js` + `paraglideVitePlugin` (see §2) |
| Cookie visible on subdomains unexpectedly (or not) | `cookieDomain` semantics changed in 2.x | Set `cookieDomain` explicitly if you need subdomain sharing |

---

## 10. Version Compatibility Notes

- **Paraglide JS 2.x** (`@inlang/paraglide-js`, currently v2.25.x) is the supported line for Svelte 5 / SvelteKit 2; it replaced the 1.x adapter architecture with a single Vite plugin, `hooks.ts` `reroute`, and `hooks.server.ts` middleware.
- The 1.x → 2.x migration drops framework-specific glue (`$lib/paraglide` layout differs, strategy/routing config moved into compiler options) — budget for a real refactor of hooks and imports, not a dependency bump.
- **Svelte 5 minimum alignment:** use `$app/state` (`page`, not `$page`), snippets for `ParaglideMessage`, and `.svelte.ts` modules for any client-side locale-adjacent state. Paraglide's runtime is framework-agnostic and emits no Svelte-specific reactivity — all Svelte 5 ergonomics come from how you structure components around `getLocale()`/`{ locale }` options.

---

## Appendix A — Verified Sources

- Official SvelteKit guide (setup, middleware, reroute, SSG, troubleshooting): paraglidejs.com/sveltekit
- Svelte CLI paraglide add-on: svelte.dev/docs/cli/paraglide
- Docs source (basics, strategy, i18n-routing, middleware, SSR, SSG, markup, configuration): github.com/opral/paraglide-js/tree/main/docs
- Svelte markup adapter (`ParaglideMessage` + snippets): github.com/opral/paraglide-js/tree/main/framework/svelte
- Package versions & deprecation notices: npm `@inlang/paraglide-js`, deprecated adapter
- 2.0 migration experience: dropanote.de migration guide, community dev-server feedback
- Svelte 5 runes guidance: svelte.dev runes docs, Mainmatter runes-and-global-state, fullstacksveltekit runes guide
