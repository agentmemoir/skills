// Plain Svelte 5 SSR — browser entry (no SvelteKit).
// Use hydrate(), not mount(): mount() is for client-only apps and replaces
// the server-rendered markup instead of attaching to it.
import { hydrate } from 'svelte';
import App from './App.svelte';

const propsElement = document.getElementById('app-props');

hydrate(App, {
  target: document.getElementById('app'),
  // Props were JSON-escaped by renderPage (see assets/entry-server.js).
  props: propsElement ? JSON.parse(propsElement.textContent) : {}
});
