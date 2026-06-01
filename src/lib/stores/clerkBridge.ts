import { writable } from 'svelte/store';

/**
 * Holds the Clerk session JWT pushed in from an allowlisted parent
 * via the `rm:clerk-token` postMessage handshake (M1 of the iframe
 * bridge — see `bridge/clerkToken.ts` and ADR-0025).
 *
 * The token lives in module-level memory, NOT localStorage. Safari
 * ITP and Chrome's 3PC deprecation partition third-party storage in
 * a way that makes it unsafe to rely on across navigations: the
 * parent is the source of truth, and each iframe load starts fresh
 * after sending `rm:chatbot-ready`.
 *
 * Two ways to read it:
 *  - `getBearerToken()` — synchronous module-level read; used by the
 *    fetch proxy and the socket auth path where reactive updates
 *    aren't needed.
 *  - `bearerToken` Svelte store — for components that want to react
 *    when the token changes (e.g. to refresh stale views after a
 *    parent-driven sign-in).
 *
 * Both views always agree because the setter updates both.
 */

let _bearerToken: string | null = null;

export const bearerToken = writable<string | null>(null);

export function setBearerToken(token: string): void {
	_bearerToken = token;
	bearerToken.set(token);
}

export function clearBearerToken(): void {
	_bearerToken = null;
	bearerToken.set(null);
}

export function getBearerToken(): string | null {
	return _bearerToken;
}

export function hasBearerToken(): boolean {
	return _bearerToken !== null;
}
