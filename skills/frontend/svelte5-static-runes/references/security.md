# Security Checklist — Static Svelte 5 Apps

A static-only app has no server to add a security layer at request time, so every one of these has to be handled in the code that ships to the browser, or in host-level static config (headers files). Nothing here is exotic — it's the standard client-side web security list, scoped to what actually matters for a Svelte/Vite static build.

## 1. XSS via `{@html}`

Svelte auto-escapes every `{expression}` in a template. `{@html ...}` is the one construct that deliberately bypasses escaping, and it is consequently the primary XSS vector in Svelte apps. Any HTML that ultimately originated from a user, a CMS, an API response, or query-string/URL data must be sanitized immediately before it reaches `{@html}` — not sanitized once "earlier in the pipeline" where a later refactor could reintroduce raw data.

```svelte
<script>
  import DOMPurify from 'dompurify';
  let { userContent } = $props();
  let sanitized = $derived(DOMPurify.sanitize(userContent, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'li'],
    ALLOWED_ATTR: ['href', 'target', 'rel']
  }));
</script>
{@html sanitized}
```

Notes:
- Use an **allowlist** (`ALLOWED_TAGS`/`ALLOWED_ATTR`), not a denylist — denylists miss variants (e.g. blocking `<script>` doesn't stop `onerror=` attributes or `javascript:` URLs).
- `DOMPurify.sanitize` is synchronous and cheap enough to call inside a `$derived`, which keeps the sanitization co-located with the render and guarantees it re-runs if the input changes.
- If the content is Markdown rendered to HTML (common case), sanitize the *output* HTML, not the Markdown source — a Markdown renderer can itself emit raw HTML passthrough that needs catching downstream.
- `assets/SecureHtml.svelte` bundles this pattern as a drop-in component.
- If you truly don't need to render arbitrary HTML (most "rich text" use cases are actually just bold/italic/links), skip `{@html}` entirely and use a constrained markup mini-language or component-based rendering instead — the safest amount of raw HTML rendering is none.

## 2. `javascript:` URLs and unsafe links

Svelte does not block `javascript:` in `href`. If a link's target is dynamic (user profile URL, CMS-provided link, query param), validate the scheme:

```js
function safeHref(url) {
  try {
    const u = new URL(url, window.location.origin);
    return ['http:', 'https:', 'mailto:'].includes(u.protocol) ? u.href : '#';
  } catch {
    return '#';
  }
}
```

For any `target="_blank"` link, add `rel="noopener noreferrer"` — without it the opened page gets a `window.opener` reference back to your app, which is a known tab-nabbing vector (the opened page can navigate your original tab to a phishing page).

## 3. Secrets and environment variables

Vite inlines any env var whose name matches `envPrefix` (default: `VITE_`) directly into the built JS as a string literal — anyone can read it from the shipped bundle with the browser devtools, no exploit needed. SvelteKit's equivalent is `$env/static/public` / `PUBLIC_`-prefixed vars; anything without that prefix is meant to stay server-only, which for a static-only app (no server at request time) means **it cannot be used by the app at runtime at all** — it can only be consumed at build time (e.g. baking pre-fetched data into the build).

Rules:
- Never put an API key, database credential, or any bearer token behind a `VITE_`/`PUBLIC_` prefix and call a protected API directly from the client.
- If the app genuinely needs to call an authenticated third-party API, the key belongs behind a separate proxy the user controls (a small serverless function, Cloudflare Worker, etc.) that injects the real credential server-side — that's a different deployment from the static site itself, so flag it explicitly rather than wiring the key into client code to make the immediate task "work."
- Some services intentionally issue "publishable"/domain-restricted keys designed to be public (e.g. certain Stripe, Firebase, or mapping-provider keys) — those are fine in a `VITE_` var, but confirm with the user (or the provider's docs) that the specific key is meant to be public rather than assuming.
- `.env.local` (git-ignored by Vite's default `.gitignore` template) is for local secrets used only in `vite.config.ts`/build tooling — never re-export those into client code via a `VITE_` alias.

## 4. Content-Security-Policy on a server-less host

You can't send an HTTP response header without a server, but static hosts support CSP two other ways:

**a) `<meta http-equiv>` tag** (works everywhere, including `file://`, but can't set some directives like `frame-ancestors` or use `report-uri`):
```html
<!-- app.html or index.html, in <head> -->
<meta http-equiv="Content-Security-Policy"
  content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.example.com; object-src 'none'; base-uri 'self';">
```
`style-src 'unsafe-inline'` is often unavoidable with Svelte's scoped styles unless you adopt a nonce/hash-based approach — Svelte-generated `<style>` tags don't carry the same risk profile as inline event-handler attributes, but tighten this if the app's threat model calls for it.

**b) Host header-config file** (real HTTP header, more capable — supports `frame-ancestors`, reporting, etc.). See `assets/_headers` for a Netlify/Cloudflare Pages template. Vercel uses `vercel.json` `headers` entries instead; S3+CloudFront needs a CloudFront response-headers policy.

Prefer (b) when the host supports it — real headers can't be stripped by an injected `<meta>` tag manipulation the way an attacker-controlled DOM insertion theoretically could, and they support more directives.

## 5. LocalStorage / sessionStorage

Both are readable by any script running on the page — including an XSS payload that got through despite the above. Don't store auth tokens, session identifiers, or PII in `localStorage`/`sessionStorage` if you can avoid it; for a fully static app with no server issuing cookies, this is often unavoidable for *something* (there's no server to set an HttpOnly cookie for you), so at minimum:
- Never store long-lived credentials there — prefer short-lived tokens with rotation if the backend supports it.
- Treat anything placed in storage as something an XSS bug would leak, and size your CSP/sanitization effort accordingly.

## 6. Dependency security

A static site ships every dependency's code straight to end users' browsers — there's no server-side isolation. Before shipping:
```bash
npm audit
npm audit fix
```
Commit the lockfile (`package-lock.json`/`pnpm-lock.yaml`) so builds are reproducible and you're not silently pulling a newly-compromised patch version. For anything embedding third-party scripts via `<script src="https://...">` (analytics, widgets), add Subresource Integrity (`integrity="sha384-..."` + `crossorigin="anonymous"`) when the provider publishes hashes, so a compromised CDN can't silently swap the script content.

## 7. Trusted Types (defense in depth, Chromium-based browsers)

If the app is high-value enough to warrant it, add a Trusted Types CSP directive (`require-trusted-types-for 'script'`) and route all DOM-injection through a Trusted Types policy — this makes it a compile-time/runtime error to pass a raw string to `innerHTML`-equivalent sinks anywhere in the app, including in third-party code, catching mistakes that manual review misses. DOMPurify has built-in Trusted Types support. This is an enhancement, not a substitute for sanitizing `{@html}` input.

## Pre-ship checklist

- [ ] Every `{@html}` usage sanitizes untrusted input immediately before render (DOMPurify with an explicit allowlist)
- [ ] No `VITE_`/`PUBLIC_`-prefixed env var contains a real secret
- [ ] CSP is set via `<meta>` and/or a host headers file
- [ ] Dynamic `href`/`src` values are scheme-validated if they can originate from user/API data
- [ ] `target="_blank"` links include `rel="noopener noreferrer"`
- [ ] `npm audit` run with no unresolved high/critical findings; lockfile committed
- [ ] No `+page.server.js` / `+server.js` / hooks.server.js / form actions present if the app is meant to be static-only (these require a real server and silently break under `adapter-static`'s prerender-only model, or get skipped, depending on adapter version — either way they don't belong in a static-only deliverable)
