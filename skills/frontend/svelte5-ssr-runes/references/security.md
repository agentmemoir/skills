# Security Checklist — Server-Rendered Svelte 5

SSR gives you a real server, which means real server-side security responsibilities: secrets, sessions, CSRF, SSRF, and headers are all back in play. At the same time, everything the server sends to the browser (including all of `load`'s return value) is public. This is the standard web-security list scoped to Svelte 5 / SvelteKit SSR.

## 1. Secrets and environment variables

SvelteKit splits env vars by import path and prefix (`svelte.config.js` `env.publicPrefix` defaults to `PUBLIC_`):

- `$env/static/private` — values inlined into the **server** bundle at build time. Fine for secrets, but build-time only; changing the value needs a rebuild.
- `$env/dynamic/private` — read from `process.env` at **runtime** (server only). Use for secrets that must rotate without a rebuild.
- `$env/static/public` / `$env/dynamic/public` — only `PUBLIC_`-prefixed vars; these are embedded in the HTML and client JS. Never put a secret here.

Rules:

- Only import private env modules from `+page.server.js`, `+layout.server.js`, `+server.js`, `hooks.server.*`, or modules under `$lib/server/`.
- `$lib/server/` and `*.server.js` are poisoning guardrails: importing them from client code is a build error. Use them for DB clients and anything secret-adjacent.
- Anything returned from `load` is serialized into the HTML payload. A field you never render is still visible in the page source. Select only the columns the client needs; keep password hashes, tokens, internal notes, and other users' data out of the return value entirely.
- In a SvelteKit app, Vite's own `VITE_`-prefixed vars are also client-visible. Do not use them for secrets.
- `.env` files stay out of git; `.env.example` documents the shape.

## 2. Content-Security-Policy with nonces

SvelteKit generates inline scripts on every page, so a naive `script-src 'self'` breaks the app. Configure CSP and let SvelteKit add nonces:

```js
// svelte.config.js
kit: {
  csp: {
    mode: 'auto', // nonces for dynamically rendered pages, hashes for prerendered pages
    directives: {
      'default-src': ['self'],
      'script-src': ['self'],
      'style-src': ['self', 'unsafe-inline'],
      'img-src': ['self', 'data:', 'https:'],
      'connect-src': ['self'],
      'object-src': ['none'],
      'base-uri': ['self'],
      'frame-ancestors': ['self']
    },
    reportOnly: {
      'script-src': ['self'],
      'report-uri': ['/csp-report']
    }
  }
}
```

- Every SvelteKit-generated inline `<script>` gets the nonce automatically (dynamically rendered pages). Manual tags in `src/app.html` need `nonce="%sveltekit.nonce%"`.
- Prerendered pages cannot use nonces (there is no per-request server), so SvelteKit uses hashes there. `mode: 'auto'` handles both. Using nonces on prerendered pages is forbidden because it would be insecure.
- Svelte transitions create inline `<style>` elements. If you use them, keep `style-src 'unsafe-inline'` or omit `style-src`; tightening it will break transitions.
- Prerendered pages get CSP via a `<meta http-equiv>` tag, which cannot express `frame-ancestors`, `report-uri`, or `sandbox` — send those from a real server route or the host.
- Do not set a second CSP in `hooks.server.ts` on top of `kit.csp`; duplicated policies only cause confusing failures.
- `reportOnly` is the way to roll out a stricter policy without breaking the app.

## 3. XSS and `{@html}`

Svelte escapes everything in `{expression}`; `{@html ...}` deliberately does not. Server-rendered is **not** sanitized — if the HTML originates from a user, a CMS, an API, or a URL, sanitize it immediately before rendering:

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

- Use an allowlist, not a denylist. If you render Markdown, sanitize the rendered HTML output, not the Markdown source.
- Validate URL schemes for dynamic `href`/`src` (`javascript:` is not blocked by Svelte); add `rel="noopener noreferrer"` to `target="_blank"` links.
- The same escaping rules apply in plain `svelte/server` SSR; nothing about rendering server-side makes `{@html}` safe.

## 4. CSRF

SvelteKit checks the `origin` header on `POST`/`PUT`/`PATCH`/`DELETE` form submissions in production by default. Leave it on. To allow a trusted third party (payment gateway, identity provider) to post to your app, list it explicitly:

```js
kit: {
  csrf: { trustedOrigins: ['https://payment-gateway.example'] } // or ['*'] to disable — don't
}
```

`+server.js` mutation endpoints that accept JSON/fetch requests do not have that protection automatically — check the origin yourself, or require a token. Same-site cookies (`sameSite: 'lax'` or `'strict'`) are a second layer, not a replacement.

## 5. Auth and sessions

- Validate sessions in `hooks.server.ts` and put the user on `event.locals`. Layout `load` functions do not run on every client-side navigation and run concurrently with page loads, so an auth check only in a layout can be bypassed or produce data leaks.
- Session cookies: `httpOnly: true`, `secure: true` in production, `sameSite: 'lax'`, a sensible `path` and `maxAge`. Use `cookies.set(...)` from an action or server route; never ship tokens to client JS.
- On logout, invalidate the session server-side and delete the cookie; do not just clear client state.
- Because `load` data is serialized into the page, assume the authenticated user can read every field returned to their browser — that is fine for their own data, wrong for anything cross-user.
- Open redirects: never pass user input (`url.searchParams.get('next')`) straight into `redirect(303, ...)`. Allowlist relative paths or known hosts.

## 6. SSRF (server-side request forgery)

Once `fetch` runs on the server, a URL that came from a user (avatar importer, webhook tester, link preview) can hit internal services or cloud metadata. Allowlist hosts and schemes, reject private IP ranges and link-local addresses, and set timeouts. Do not use server `fetch` as an open proxy.

## 7. Error handling and leakage

- `handleError` transforms unexpected errors before they reach the client. Return a generic `{ message }` and log the real one server-side. Thrown errors otherwise expose stack traces and internal messages in the error page and response.
- `error(status, message)` messages are shown to users — write them as user-facing copy; keep database details out.
- In development, Svelte and SvelteKit errors are verbose on purpose; do not copy dev output into production responses.

## 8. Streaming caveats

Headers and status are fixed once streaming starts. Do not call `setHeaders` or throw `redirect` inside a streamed promise, and attach a noop `.catch(() => {})` to promises not created by SvelteKit's `fetch` so a rejection before render cannot crash the server. This is a correctness and availability issue, not just polish.

## 9. Dependencies

SSR apps ship dependencies to both the server and the browser. Before shipping: `npm audit`, commit the lockfile, and for third-party `<script src="https://...">` tags use Subresource Integrity (`integrity="sha384-..."` + `crossorigin="anonymous"`) where the provider publishes hashes.

## Pre-ship checklist

- [ ] No secret is behind a `PUBLIC_`/`VITE_` prefix; private imports live only in server files or `$lib/server`
- [ ] Every `load` return value contains only fields the browser is allowed to see
- [ ] `kit.csp` is configured; manual `app.html` tags use `%sveltekit.nonce%`; no duplicate CSP in hooks
- [ ] Every `{@html}` sanitizes untrusted input immediately before render (DOMPurify allowlist)
- [ ] Dynamic `href`/`src` values are scheme-validated; `target="_blank"` links use `rel="noopener noreferrer"`
- [ ] Auth/session check runs per request (hooks and/or `+page.server.js`), not only in a layout `load`
- [ ] Session cookies are `httpOnly` + `secure` + `sameSite`; logout invalidates server-side
- [ ] CSRF protection left enabled; custom mutation endpoints check origin
- [ ] Server-side fetches of user-supplied URLs are allowlisted (SSRF)
- [ ] `handleError` returns generic messages; no stack traces or secret values reach the client
- [ ] Streamed promises have rejection handling; no `setHeaders`/`redirect` after streaming begins
- [ ] `npm audit` clean; lockfile committed
