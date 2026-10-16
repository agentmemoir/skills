import type { Handle, HandleServerError } from '@sveltejs/kit';

// Type the session user in src/app.d.ts:
//
// declare global {
//   namespace App {
//     interface Locals { user: { id: string; name: string } | null }
//   }
// }
// export {};
//
// Then `event.locals.user` is typed everywhere on the server.

export const handle: Handle = async ({ event, resolve }) => {
  const sessionId = event.cookies.get('session');
  event.locals.user = sessionId ? await getUserFromSession(sessionId) : null;

  const response = await resolve(event);

  // CSP is sent by kit.csp in svelte.config.js — do not add a second one here.
  response.headers.set('x-content-type-options', 'nosniff');
  response.headers.set('referrer-policy', 'strict-origin-when-cross-origin');
  response.headers.set('permissions-policy', 'camera=(), microphone=(), geolocation=()');

  return response;
};

export const handleError: HandleServerError = ({ error, status }) => {
  console.error(error);
  // Returned to the client and rendered in +error.svelte.
  // Never include stack traces, SQL, or secret values.
  return { message: status === 404 ? 'Not found' : 'Something went wrong' };
};

async function getUserFromSession(sessionId: string) {
  // Replace with a real session lookup (database / cache).
  return { id: sessionId, name: 'Demo User' };
}
