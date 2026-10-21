// Plain Svelte 5 SSR — server entry (no SvelteKit).
//
// Build:
//   vite build --outDir dist/client
//   vite build --outDir dist/server --ssr src/entry-server.js
//
// The client build rewrites index.html to link the hashed JS entry and CSS it
// emitted, so the production template must be read from dist/client/index.html.
// Never hardcode /src/entry-client.js in a template you serve from a production
// build: that path only exists under the Vite dev server.
//
// Dev:  read the root index.html and apply `vite.transformIndexHtml(url, template)`,
//       then load this file with `vite.ssrLoadModule('/src/entry-server.js')`.
// Prod: read dist/client/index.html and import this file from dist/server.
//
// The template needs the <!--app-head--> and <!--app-html--> placeholders and the
// __APP_PROPS__ token (see assets/index.html).
import { render } from 'svelte/server';
import App from './App.svelte';

export async function renderPage(template, props = {}) {
  // Await is required only with experimental.async, but render() is promise-like
  // in both modes, so awaiting always works.
  const { head, body } = await render(App, { props });

  return template
    .replace('<!--app-head-->', () => head)
    .replace('<!--app-html-->', () => body)
    .replace('__APP_PROPS__', () => safeJson(props));
}

function safeJson(value) {
  // Escape `<` so a prop containing `</script>` cannot break out of the tag.
  // For richer values (Date, Map, Set), use devalue instead.
  return JSON.stringify(value).replace(/</g, '\\u003c');
}
