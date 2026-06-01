/**
 * Clerk-Bearer postMessage handshake — M1 of the chatbot iframe-bridge
 * programme (ADR-0025). The chatbot iframe accepts a Clerk session JWT
 * pushed in by an allowlisted `*.datameesters.nl` parent and uses it
 * as `Authorization: Bearer ...` on every fetch + the Socket.IO
 * handshake. This avoids relying on third-party cookies, which Safari
 * ITP and Chrome 3PC deprecation make unreliable.
 *
 * Co-exists with the `bridge/geoportaal.ts` PRD-0023 protocol and
 * Databank's `rm:chatbot:context` protocol on the same message channel;
 * each protocol discriminates on `event.data.type`.
 *
 * The parent side is the source of truth: it pushes a fresh token on
 * Clerk session refresh, and the iframe never persists the token across
 * reloads. Each iframe load starts blank, sends `rm:chatbot-ready`,
 * and waits for the parent to push.
 */

export const CLERK_TOKEN_PROTOCOL_VERSION = 1 as const;

export interface ClerkTokenMessage {
	type: 'rm:clerk-token';
	token: string;
}

export interface ClerkTokenClearedMessage {
	type: 'rm:clerk-token-cleared';
}

export interface ChatbotReadyMessage {
	type: 'rm:chatbot-ready';
	iframeVersion: string;
	protocolVersion: typeof CLERK_TOKEN_PROTOCOL_VERSION;
}

/**
 * Origins the iframe accepts a Clerk JWT FROM. Mirrors the
 * `*.datameesters.nl` host envelope but with explicit entries —
 * wildcard matching on origins is the classic mistake that lets a
 * `evil-datameesters.nl.attacker.com` masquerade.
 *
 * Localhost ports are dev-only and stripped in production builds via
 * the import.meta.env.PROD guard below.
 */
const PRODUCTION_TOKEN_ORIGINS = [
	'https://datameesters.nl',
	'https://geoportaal.datameesters.nl',
	'https://digitaltwin.datameesters.nl',
	'https://databank.datameesters.nl',
	'https://chat.datameesters.nl'
];

const DEV_TOKEN_ORIGINS = ['http://localhost:3000', 'http://localhost:5173', 'http://localhost:8080'];

export function getAllowedTokenOrigins(): readonly string[] {
	// Vite replaces import.meta.env.PROD at build time; in production the
	// dev origins are dead-code-eliminated, so a prod bundle can never
	// accept a token from localhost even if someone proxies a parent there.
	if (typeof import.meta !== 'undefined' && import.meta.env?.PROD) {
		return PRODUCTION_TOKEN_ORIGINS;
	}
	return [...PRODUCTION_TOKEN_ORIGINS, ...DEV_TOKEN_ORIGINS];
}

export function isAllowedTokenOrigin(origin: string): boolean {
	return getAllowedTokenOrigins().includes(origin);
}

/**
 * Validate an incoming MessageEvent's `data` as the rm:clerk-token
 * payload. Returns the parsed payload or `null` — the caller MUST
 * additionally check `isAllowedTokenOrigin(event.origin)` before
 * trusting the token.
 *
 * The token is intentionally not deep-validated here — Clerk's
 * backend JWKS verification is the source of truth via
 * `_try_clerk_jwt_auth` in `utils/auth.py`. The frontend just
 * needs a non-empty bearer string to forward.
 */
export function parseClerkTokenMessage(data: unknown): ClerkTokenMessage | null {
	if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
	const d = data as Record<string, unknown>;
	if (d.type !== 'rm:clerk-token') return null;
	if (typeof d.token !== 'string' || d.token.length === 0) return null;
	return { type: 'rm:clerk-token', token: d.token };
}

/**
 * Validate an incoming MessageEvent's `data` as a token-cleared
 * signal. The parent emits this when the user signs out on the parent
 * side; the iframe drops its in-memory token and lets requests fall
 * through to the existing localStorage/cookie path (which will fail,
 * surfacing a sign-in prompt — the desired UX).
 */
export function parseClerkTokenClearedMessage(data: unknown): ClerkTokenClearedMessage | null {
	if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
	const d = data as Record<string, unknown>;
	if (d.type !== 'rm:clerk-token-cleared') return null;
	return { type: 'rm:clerk-token-cleared' };
}

/**
 * Post `rm:chatbot-ready` to the parent so it knows when to push the
 * first token. Avoids the race where the parent pushes before the
 * iframe's message listener is registered. No-op when not in iframe
 * context, when the parent origin isn't allowlisted, or when called
 * from a non-browser environment.
 *
 * `targetOrigin` is required for security: postMessage with `'*'`
 * would broadcast to whatever currently controls the parent, which
 * defeats the allowlist.
 */
export function sendChatbotReady(parentOrigin: string, iframeVersion: string): boolean {
	if (typeof window === 'undefined') return false;
	if (!window.parent || window.parent === window) return false;
	if (!isAllowedTokenOrigin(parentOrigin)) return false;
	const message: ChatbotReadyMessage = {
		type: 'rm:chatbot-ready',
		iframeVersion,
		protocolVersion: CLERK_TOKEN_PROTOCOL_VERSION
	};
	try {
		window.parent.postMessage(message, parentOrigin);
		return true;
	} catch {
		return false;
	}
}
