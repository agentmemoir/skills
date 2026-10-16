# Runes Under SSR — Reference

Every Svelte component runs twice: once on the server to produce HTML, once in the browser to hydrate (and again on every update after that). Runes are designed to be isomorphic, but they are not all equal in both places. This file covers what each rune does on the server, the patterns that keep hydration correct, and the request-scoped state rules that prevent cross-user leaks.

## Rune-by-rune server behavior

### `$state`

The initial value renders. During a single SSR pass nothing re-renders — the server walks the tree top-down and emits HTML synchronously, so mutating state mid-render (for example in a child component) does not update already-emitted parent HTML. Do not rely on reactivity *within* a server render; rely on computed values being correct before they are read.

`$state.raw` works on the server and skips proxy creation. SvelteKit `load` data arrives as a plain object; if you assign it to `$state` it becomes a deeply reactive proxy. For large payloads you only replace wholesale, `$state.raw(data)` avoids that cost. If you later need deep mutation, use plain `$state`.

`$state.snapshot` works on the server too — useful when passing state into a non-Svelte library that should not see a Proxy.

### `$derived`

Deriveds **do** run during SSR: their values are needed to render the HTML. If a value must appear in the server response, `$derived` is the rune to put it in. Two constraints:

- Keep the expression pure and deterministic.
- It must not touch browser-only APIs. A `$derived` that reads `window`, `document`, or `localStorage` throws during SSR even though it would work in the browser.

`$derived.by` follows the same rules.

### `$effect`, `$effect.pre`, `$effect.root`

Effects **never run during SSR**. They exist to synchronize with the browser: DOM APIs, subscriptions, timers, analytics. Consequences:

- State populated only inside an effect is empty in the server HTML. The page renders a hole, then the value appears after hydration — bad for SEO, bad for first paint, and it looks like a bug even though nothing technically errored.
- Do not use `$effect` to copy `data` into local state. Let `$derived` read `data` directly.
- `$effect.root` creates an unowned scope; it still only runs in the browser. Module-level singletons built with it must not be assumed to exist on the server.

```svelte
<!-- ❌ derived work done in an effect: blank on the server -->
<script>
  let { items } = $props();
  let total = $state(0);
  $effect(() => { total = items.reduce((a, i) => a + i.price, 0); });
</script>

<!-- ✅ computed where SSR can see it -->
<script>
  let { items } = $props();
  let total = $derived(items.reduce((a, i) => a + i.price, 0));
</script>
```

If the value genuinely requires the DOM (element size, scroll position, canvas), keep it in an effect and render a stable server fallback.

### `$props` and `$bindable`

Both work normally on the server; initial values render. `data` from `load` is passed into the page component as props. Bindable values must have deterministic initial values, or the server HTML and the first client render will disagree.

### `$props.id()`

Added in Svelte 5.20. Returns an ID unique to the component instance that is **identical on the server and after hydration**. Use it whenever you need to link elements:

```svelte
<script>
  const uid = $props.id();
</script>

<label for="{uid}-email">Email</label>
<input id="{uid}-email" type="email" />
```

Alternatives such as `Math.random()`, `crypto.randomUUID()`, or a module-level counter produce different values on server and client and cause hydration mismatches.

### `$inspect`, `$host`, `$effect.tracking`

Development or custom-element tools; none produce SSR output. `$effect.tracking()` compiles to the literal `false` on the server (the server transform replaces it, it is not a runtime check), so it is always false during SSR.

### `untrack`

Works on the server like any function. It matters less because effects do not run there, but shared utility functions that use it should still be safe when called during render.

## Hydration-safe values

Hydration compares the server HTML with the client's first render. The rule of thumb: **anything read during render must produce the same value in Node/edge and in the browser.**

| Don't render | Do instead |
|---|---|
| `new Date().toLocaleString()` | Format the date in `load` and pass the string, or always pass an explicit `timeZone` to `Intl.DateTimeFormat` — server and client timezones differ. |
| `Date.now()` timestamps | Generate in `load`, or use a `mounted` flag with a server fallback. |
| `Math.random()` / `crypto.randomUUID()` | `$props.id()` for DOM ids; generate real randomness in `load` and pass it as a prop. |
| `localStorage` / `sessionStorage` reads | Default in `$state`, read in `$effect`/`onMount` after hydration; or read a cookie in `load` when SSR needs the value. |
| `window.matchMedia(...)` in markup | Prefer a CSS media query; otherwise start from a default and correct it in an effect. |
| `window.innerWidth`, `navigator.*` in markup | Same: default plus effect, or derive in `load` from request headers when it must be server-side. |
| `browser`/`typeof window` checks that fork markup | Gate on a `mounted` flag so both sides render the fallback, then swap after mount. |
| `{@html}` whose content differs between server and client | Sanitize/format once, on the server, and pass the final HTML down. |

A `mounted` flag is the standard pattern for genuinely client-only markup:

```svelte
<script>
  let mounted = $state(false);
  $effect(() => { mounted = true; });
</script>

{#if mounted}
  <ClientOnlyWidget />
{:else}
  <div class="widget-placeholder"></div>
{/if}
```

The server renders the placeholder; the client's first render matches it; the effect flips `mounted` after hydration. No mismatch.

### Debugging a mismatch

In development Svelte logs `hydration_mismatch` ("Hydration failed because the initial UI does not match what was rendered on the server"), usually preceded by a `console.error` showing the offending HTML. It cannot be suppressed with `svelte-ignore` — that is deliberate, because a mismatch means Svelte had to discard and re-render the DOM.

Common causes, in order of frequency:

1. Browser-only values in the render path (the table above).
2. Invalid HTML nesting that the browser repairs (`<div>` inside `<p>`, `<h1>` inside `<p>`, block content inside `<a>`), shifting the DOM tree before hydration can match it. The dev server reports the component and line for these.
3. `{#await}` over a promise that resolves to different values on server and client.
4. Third-party DOM mutation (browser extensions, embedded scripts) before hydration.
5. Random or time-based IDs and keys.

## Request-scoped state

Servers are long-lived and shared across users. A module-level `$state` value is created once per server process, so it is shared by every request that process handles. That is fine for client-only app state and a data leak for anything personalized.

Three patterns, from most local to most shared:

```ts
// 1. Client-only app state (theme, UI flags) — module class is fine, never user data
// src/lib/theme.svelte.ts
class Theme {
  current = $state<'light' | 'dark'>('light');
  toggle = () => (this.current = this.current === 'light' ? 'dark' : 'light');
}
export const theme = new Theme();
```

```svelte
<!-- 2. Request data from load, shared through context — per request, safe -->
<!-- +layout.svelte -->
<script>
  import { setContext } from 'svelte';
  let { data } = $props();
  setContext('user', () => data.user); // pass a getter, not the value, to keep reactivity
</script>
```

```ts
// 3. Data many server functions need — event.locals, populated in hooks.server.ts
// src/hooks.server.ts
export const handle = async ({ event, resolve }) => {
  const session = event.cookies.get('session');
  event.locals.user = await getUserFromSession(session);
  return resolve(event);
};
```

Notes:

- `getContext` must be called during component initialization, not inside an event handler or after an `await`.
- Passing the raw value into `setContext` freezes it at set time; pass `() => value` or an object with getters so consumers read the current value.
- During SSR, state updates do not propagate upward: a child that mutates context state mid-render cannot change what an already-rendered parent shows. The client behaves the opposite way. This is why passing data down (props/context getters) avoids hydration "flashes"; pass values down rather than mutating them upward.
- Keep `load` pure. Writing to a module store inside `load` is a per-process leak, exactly like the module-level `$state` case.
- `getRequestEvent()` from `$app/server` lets shared server helpers (like auth guards) access `locals`, `url`, and `cookies` without passing `event` around.

## Plain Svelte SSR (no SvelteKit)

Svelte exposes the SSR pieces directly for existing backends. This is what SvelteKit does for you, so use these only when SvelteKit is not in the picture.

```js
// server side
import { render } from 'svelte/server';
import App from './App.svelte';

const { head, body } = await render(App, {
  props,
  context: new Map(),   // optional: provide context values
  idPrefix: 'app',      // optional: prefix for $props.id(), avoids collisions across multiple roots
  csp: { nonce }        // optional: nonce Svelte should use for its inline scripts/styles
});
```

```js
// browser side
import { hydrate } from 'svelte';
import App from './App.svelte';

hydrate(App, { target: document.getElementById('app'), props });
```

Key points:

- `render` returns `{ head, body, hashes }`. `head` goes in `<head>`, `body` where the app should mount. (`html` still exists but is deprecated in favor of `body`.)
- The return value is promise-like. Without async mode it resolves synchronously; with `experimental.async` enabled, `await render(...)` waits for component `await` expressions. Awaiting is harmless in both modes.
- Use `hydrate`, not `mount`, when the markup came from the server. `mount` is for client-only rendering and will replace the server HTML.
- `csp.hash: true` makes Svelte report SHA-256 hashes for its inline scripts/styles in `hashes`, for a hash-based Content-Security-Policy instead of a nonce.
- Server-side code here has no `$app/*` modules: use `typeof window !== 'undefined'`, not `browser` from `$app/environment`.
- When serializing props into the page, put them in a `<script type="application/json">` tag and escape `<` (for example `JSON.stringify(props).replace(/</g, '\\u003c')`) or use `devalue`; otherwise a prop containing `</script>` breaks out of the tag. `assets/entry-client.js` reads that JSON tag back on hydration.

`assets/index.html`, `assets/entry-server.js`, and `assets/entry-client.js` are ready-to-copy versions of the whole plain-SSR triangle. The template comes from the built client HTML (`dist/client/index.html`) in production — it already links the hashed JS and CSS — and from `vite.transformIndexHtml(url, template)` in dev; see `references/ssr-build.md` for the exact build commands.

## Async SSR, `await`, and remote functions (experimental)

Status as of September 2026: Svelte 5.57, SvelteKit 2.7x. Async support is still opt-in and not subject to semver; SvelteKit 3 is in release candidate. Treat this section as "know it exists and how to spot it", not as production guidance.

Enable it (only when the user asks) in `svelte.config.js`:

```js
export default {
  compilerOptions: { experimental: { async: true } }
};
```

What it allows (await expressions: Svelte ≥ 5.36; async SSR: Svelte ≥ 5.39.3 with SvelteKit ≥ 2.43):

- `await` at the top level of a component's `<script>`, inside `$derived(...)`, and inside markup.
- During SSR, `await` expressions **not** wrapped in a `<svelte:boundary>` with a `pending` snippet block until they resolve; those inside such a boundary render the pending snippet and skip the content.
- Independent awaits run in parallel.
- With remote functions (SvelteKit `experimental.remoteFunctions`), results fetched during SSR are serialized into the HTML and reused during hydration instead of being fetched twice — in the common case. The async-SSR PR lists cases where an extra round trip still occurs (for example a call inside an `{#if await ...}` block) and notes hydration is slightly buggy; treat reuse as best-effort while the feature is experimental.

Related APIs that appear in this mode: `$effect.pending()` (count of pending promises in the current boundary), `settled()` (promise that resolves when the current update is complete), and `fork()` (start async work you expect to need, for preloading).

Caveats to repeat to users: APIs can change outside semver majors, effects reorder slightly (`{#if}`/`{#each}` block effects before `$effect.pre`), and streaming of boundary content is planned but not shipped. Do not build a production architecture on it yet.

### Keeping this current

Status checked 2026-09-11 (Svelte 5.57, SvelteKit 2.70.x, SvelteKit 3 in RC). Before changing any guidance in this section, re-check these sources:

- `svelte.dev/docs/svelte/await-expressions` — the experimental flag and its caveats; the flag is removed in Svelte 6.
- `svelte.dev/docs/kit/remote-functions` — the remote functions flag and API surface.
- `svelte.dev/blog` — the monthly "What's new in Svelte" posts announce stabilization and breaking changes.
- `packages/svelte/CHANGELOG.md` in the svelte repo — the first release that drops the `experimental.async` flag.

## Svelte 4 → 5 SSR migration notes

- `export let data` → `let { data } = $props()`; layout/page props have generated types like `PageProps` / `LayoutProps` (SvelteKit 2.16+).
- `$:` statements that computed SSR-visible values → `$derived` (not `$effect`). A `$:` block with a side effect → `$effect`, which will no longer run during SSR.
- `$app/stores` reads (`$page`) → `$app/state` (`page`), imported directly; this works on SvelteKit 2.12+ and is the direction for 3.
- Component-level stores → runes; watch the cross-request rules above and prefer context/`load` over module scope for anything user-specific.
- `onMount`/`onDestroy` never ran during SSR and still do not; nothing to change, but do not move SSR-visible computation into them.
- `<svelte:component this={X}>` is no longer needed — components are dynamic by default in runes mode.
- `npx sv migrate svelte-5` (the current CLI; older docs say `svelte-migrate`) handles mechanical rewrites. Review the diff: it cannot tell a `$:` block that should be `$derived` from one that should be `$effect`, and it does not fix module-level state that leaks across requests.
