# URL State for Tabs, Filters, and Shallow Routing

UI state that must survive reload, back/forward, and a shared link (active tab, filters, sort order, page number) belongs in the query string. This file targets SvelteKit 3.x and gives the 2.x equivalent in parentheses. Plain Vite has no `page` object — see "No SvelteKit" at the end.

## The one rule

The URL drives the UI. Derive the value with `$derived`; never copy it into `$state` once at init.

```svelte
<script>
  import { page } from '$app/state';

  const tab = $derived(page.url.searchParams.get('tab') ?? 'overview');
</script>
```

A one-time copy freezes the first render and ignores back/forward:

```svelte
<!-- ❌ wrong — the tab never changes after load -->
<script>
  let tab = $state(page.url.searchParams.get('tab') ?? 'overview');
</script>
```

## What `page.url` actually means

`page.url` describes the page that is *rendered*. It is accurate after every real navigation: `goto`, a link click, back and forward.

It is **not** the address-bar URL after a shallow write. In 3.x a shallow navigation fills `page.shallow` with `{ url, params, route }` and deliberately leaves `page.url` describing the rendered page. In 2.x, `replaceState`/`pushState` update `page.state` and never assign `page.url`.

That gap produces the classic bug: the tab bar derives from `page.url`, the click handler performs a shallow write, the address bar changes, and the tabs do not.

| Need | 3.x | 2.x |
|---|---|---|
| Read the visible URL | `page.shallow?.url ?? page.url` | `page.state` after a shallow write, otherwise `page.url` |
| Shallow write, page stays rendered | `goto(url, { shallow: true })` | `replaceState(url, state)` |
| Real navigation, no history entry | `goto(url, { replace: true })` | `goto(url, { replaceState: true })` |
| Keep scroll position and focus | `goto(url, { reset: false })` | `goto(url, { noScroll: true, keepFocus: true })` |

3.x renamed the options: `replaceState` became `replace`, and `noScroll: true` plus `keepFocus: true` collapsed into `reset: false` (`reset` defaults to true, which restores scroll and focus on every navigation). `replaceState` and `pushState` from `$app/navigation` still exist but are deprecated in favour of `goto(..., { shallow: true })`. In 3.x, `page.url` is a `ReadonlyURL`: `page.url.searchParams.set(...)` is a type error, so copy it with `new URL(page.url)` before mutating.

Do not reach for `window.location.href` as a general base. `page.url` is the only URL source that exists during prerender and build, where there is no `window` at all. `location.href` is the correct base in exactly one case: SvelteKit 2.x after a shallow write, where nothing else is fresh.

## A revision counter does not fix this

Bumping a counter after a shallow write re-runs the reader, but the reader still reads the same stale `page.url`, so it returns the same old value. The counter only helps when the value being read actually changed — your own `$state`, or `page.shallow.url` in 3.x. Do not add a counter as the fix for a stale `page.url`.

## Write the URL in the event handler, not in an `$effect`

An effect that writes the URL re-runs on the state it just changed, which produces write loops and duplicate history entries, and it runs after paint. Change the URL in the handler that changed the intent:

```svelte
<script>
  import { goto } from '$app/navigation';
  import { page } from '$app/state';

  function selectTab(next) {
    const url = new URL(page.url);
    url.searchParams.set('tab', next);
    goto(url, { replace: true, reset: false });
  }
</script>
```

## One module owns URL reads and writes

Three components each building a query string is how params get dropped. Put both directions in one `.svelte.ts` module, and build every new URL from the freshest source so earlier params survive:

```ts
// url-state.svelte.ts
import { goto } from '$app/navigation';
import { page } from '$app/state';

// The visible URL: the shallow target when one is pending, else the rendered page.
export function visibleUrl(): URL {
  return page.shallow?.url ?? page.url;          // 2.x: page.state.url ?? new URL(window.location.href)
}

export function readParam(key: string, fallback: string): string {
  return visibleUrl().searchParams.get(key) ?? fallback;
}

export function writeParams(patch: Record<string, string | null>, replace = true): void {
  const url = new URL(visibleUrl());             // copy: page.url is read-only in 3.x
  for (const [key, value] of Object.entries(patch)) {
    if (value === null) url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  }
  goto(url, { replace, reset: false });          // 2.x: replaceState(url, {}) / pushState(url, {})
}
```

## Delete default values from the URL

`?tab=overview` and no query string should mean the same thing. Delete the param when it holds its default so one canonical URL exists per view:

```ts
writeParams({ tab: next === 'overview' ? null : next });
```

Two tradeoffs to accept knowingly. Use replace, not push: canonicalizing with push fills the back button with near-identical entries. And a link that explicitly carries the old default still names it, so changing a default later changes what old links mean.

## Audit before saying done

Run these from the app root and account for every hit:

```bash
grep -rn "history\.\(push\|replace\)State" src   # outside your url-state module: a stale page.url waiting to happen
grep -rn "page\.url" src                         # each read must sit in $derived or a handler, never a one-time $state init
grep -rn "location\.href" src                    # only valid in plain Vite, or 2.x after a shallow write
grep -rn "goto(" src                             # check replace/reset options and that url is built from visibleUrl()
```

Then answer, from the diff: which single module owns URL writes, and what does the tab bar derive from when a shallow write has already happened?

## No SvelteKit (plain Vite)

There is no `page` object, so the browser is the source of truth. Read `new URL(location.href).searchParams` — never a cached copy — and write with `history.replaceState` (or `pushState` when a back entry is wanted). Native `replaceState`/`pushState` do not fire `popstate`, so subscribe to `popstate` yourself to re-render on back/forward, or use hash routing and listen to `hashchange`. In a plain SPA, `location.href` is always the correct base for a new URL.
