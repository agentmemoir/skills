# Svelte 5 Runes — Reference

Runes are compiler keywords, not functions: they are prefixed with `$`, are never imported, cannot be reassigned to a variable, and only work in specific positions (top level of `<script>`, inside `.svelte.js`/`.svelte.ts` modules). Stable since Svelte 5.0 (October 2024).

## `$state` — reactive state

```svelte
<script>
  let count = $state(0);
  let name = $state('world');
  let items = $state(['a', 'b', 'c']); // deeply reactive: items.push(...) triggers updates
</script>

<button onclick={() => count++}>Count: {count}</button>
```

- Arrays/objects passed to `$state` become deeply reactive proxies — mutating a nested property (`items[0].done = true`) triggers updates, not just reassignment.
- **`$state.raw(value)`** opts out of the proxy for large or effectively-immutable data (parsed API responses, big config blobs). Mutating a raw-stated object does *nothing*; you must reassign the whole value to trigger an update. Use this when you profile a real perf problem from proxying large structures, not by default.
- **`$state.snapshot(value)`** takes a plain-object copy of reactive state, useful when passing state into a non-Svelte API (e.g. `structuredClone`, `JSON.stringify`, a charting library) that shouldn't see a Proxy.
- Class fields can use `$state` too (in `.svelte.js`/`.svelte.ts` files), which is the standard way to build shared reactive stores — see "Cross-component state" below.

## `$derived` — computed values

```svelte
<script>
  let count = $state(0);
  let doubled = $derived(count * 2);

  // multi-statement logic needs $derived.by
  let stats = $derived.by(() => {
    const sum = items.reduce((a, b) => a + b, 0);
    return { sum, avg: sum / items.length };
  });
</script>
```

- **Must be pure.** No side effects, no mutating other state inside the derivation. If you find yourself wanting to log or fetch inside a `$derived`, that's an `$effect`.
- Read-only — you cannot assign to a `$derived` value directly (an exception is `$derived` combined with a manual override pattern using a separate `$state` flag, which is an advanced escape hatch, not the default).
- Recomputes lazily and only when a value it actually read changes — Svelte tracks dependencies by what's read during the last run, not a declared list.

## `$effect` — side effects, not derivations

```svelte
<script>
  let count = $state(0);

  $effect(() => {
    console.log('count is now', count);
    const id = setInterval(() => console.log(count), 1000);
    return () => clearInterval(id); // cleanup, runs before re-run and on unmount
  });
</script>
```

- Runs **after** the DOM updates, only in the browser (never during SSR/prerendering) — don't rely on an effect running during a prerender build step.
- Auto-tracks whatever reactive state it reads synchronously on each run. There is no dependency array to get wrong — but that also means reading state conditionally can make tracking inconsistent; keep the reads unconditional at the top of the effect where possible.
- **The most common bug: writing to the same state the effect reads.** This creates an infinite update loop and is a strong signal the logic should be a `$derived` instead.
  ```js
  // ❌ wrong — infinite loop candidate, and doubled isn't really "derived" of anything else here
  $effect(() => { doubled = count * 2; });
  // ✅ right
  let doubled = $derived(count * 2);
  ```
- **`$effect.pre`** runs before the DOM updates (rare; mainly for measuring/adjusting scroll position before a change is painted).
- **`untrack(fn)`** (imported from `'svelte'`) lets you read a value inside an effect *without* adding it as a dependency — use when you need a value's current snapshot but shouldn't re-run when it changes on its own:
  ```js
  import { untrack } from 'svelte';
  $effect(() => {
    save(data, { timestamp: untrack(() => time) }); // re-runs on `data`, not on `time`
  });
  ```
- **`$effect.root(fn)`** creates an effect scope that isn't tied to a component and doesn't auto-cleanup — for effects created outside component initialization (e.g. a module-level singleton). Returns a cleanup function you must call manually.
- **`$effect.tracking()`** returns whether the current code is running inside a tracking context — occasionally useful in shared utility functions that behave differently inside vs. outside reactive scopes.

## `$props` — component inputs

```svelte
<script>
  let { name, disabled = false, children, ...rest } = $props();
</script>
<button {disabled} {...rest}>{@render children()}</button>
```

- Replaces `export let`. Destructure with defaults exactly like a normal JS object parameter.
- `children` is how the default slot content arrives now (see Snippets below) — it's a `Snippet`, rendered with `{@render children()}`.
- TypeScript: type props with an interface/type and `let { name }: Props = $props();`, or inline `$props<{ name: string; disabled?: boolean }>()`.

### `$bindable` — two-way bindable props

```svelte
<!-- Child.svelte -->
<script>
  let { value = $bindable('') } = $props();
</script>
<input bind:value />
```
```svelte
<!-- Parent.svelte -->
<Child bind:value={parentValue} />
```
Only mark a prop `$bindable` when the child genuinely needs to mutate a value the parent owns (form controls are the classic case). Overusing bindable props re-introduces the two-way-binding coupling runes were partly designed to make explicit and opt-in — prefer a plain prop + `oninput`/callback prop when the parent doesn't need every child mutation reflected automatically.

## Snippets — replacing slots

```svelte
{#snippet row(item)}
  <li>{item.name}</li>
{/snippet}

<ul>
  {#each items as item}
    {@render row(item)}
  {/each}
</ul>
```
Snippets replace named slots and slot props. A component receiving a snippet as a prop should type it as `Snippet<[ArgType]>` (imported from `'svelte'`) in TypeScript.

## Attachments — replacing many custom actions (Svelte ≥ 5.29)

```svelte
<script>
  function tooltip(node) {
    const instance = createTooltip(node);
    return () => instance.destroy();
  }
</script>
<div {@attach tooltip}>Hover me</div>
```
An attachment is a function that runs in an effect when the element mounts (or when state it reads changes), optionally returning a cleanup function. This is the modern replacement for many `use:action` patterns and composes naturally with runes since it's just a function reading `$state`.

## Cross-component / module-level shared state

Reactivity works outside `.svelte` files as of Svelte 5, in `.svelte.js`/`.svelte.ts` modules. The standard pattern is a small class:

```ts
// counter.svelte.ts
class Counter {
  count = $state(0);
  doubled = $derived(this.count * 2);
  increment = () => this.count++;
}
export const counter = new Counter();
```
```svelte
<script>
  import { counter } from './counter.svelte.ts';
</script>
<button onclick={counter.increment}>{counter.count} / {counter.doubled}</button>
```
This replaces Svelte 4's `writable()`/`readable()` stores for most app-wide client state. Reach for plain module-level `$state` (not a class) only for the very simplest single-value case; the class form scales better once you add derived values or methods.

Because this skill is about **static-only** apps, module-level state like this is safe by default — there's no server, so there's no risk of one request's state leaking into another's (a real concern in SvelteKit SSR, where module-level state is shared across all requests unless scoped correctly). You don't need `setContext`/`getContext` request-scoping tricks here unless you specifically need per-component-tree isolation.

## `$inspect` and `$host` (dev/component-authoring tools)

- **`$inspect(value)`** logs whenever `value` changes, during development only — it's stripped in production builds. Add `.with(callback)` for custom formatting. Use it for debugging reactivity instead of scattering `$effect(() => console.log(...))`.
- **`$host()`** returns the host element when compiling a component as a custom element (`<svelte:options customElement />`) — irrelevant unless the static build is producing web components.

## Svelte 4 → 5 migration table

| Svelte 4 | Svelte 5 |
|---|---|
| `let x = 0` (implicitly reactive at top level) | `let x = $state(0)` |
| `$: y = x * 2` | `let y = $derived(x * 2)` |
| `$: { doStuff(x) }` | `$effect(() => { doStuff(x) })` |
| `export let prop` | `let { prop } = $props()` |
| `export let value` + `bind:value` from parent | `let { value = $bindable() } = $props()` |
| `on:click={handler}` | `onclick={handler}` (all DOM events lost the `on:` prefix) |
| `<slot />` / `<slot name="x" />` | `{@render children()}` / named snippet props |
| `<slot let:item>` (slot props) | snippet parameters: `{#snippet row(item)}` |
| `onMount(fn)` | `$effect(() => { fn(); })` when it's about DOM/browser setup |
| `onDestroy(fn)` | return a cleanup function from `$effect` |
| `writable(0)` + `$store` | `$state(0)` in a `.svelte.js` module (see above) |
| `use:action` | often still fine, but consider `{@attach fn}` for new code |

Run `npx sv migrate svelte-5` for the mechanical parts of a migration, then manually review: the CLI does not reliably convert store-based cross-module state into the class pattern, and it can't tell when a `$:` block should become `$derived` vs `$effect` — that's a judgment call based on whether the block has a side effect.
