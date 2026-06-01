import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
	CLERK_TOKEN_PROTOCOL_VERSION,
	getAllowedTokenOrigins,
	isAllowedTokenOrigin,
	parseClerkTokenClearedMessage,
	parseClerkTokenMessage,
	sendChatbotReady
} from './clerkToken';

describe('isAllowedTokenOrigin', () => {
	it('accepts production datameesters origins', () => {
		expect(isAllowedTokenOrigin('https://datameesters.nl')).toBe(true);
		expect(isAllowedTokenOrigin('https://geoportaal.datameesters.nl')).toBe(true);
		expect(isAllowedTokenOrigin('https://databank.datameesters.nl')).toBe(true);
		expect(isAllowedTokenOrigin('https://digitaltwin.datameesters.nl')).toBe(true);
		expect(isAllowedTokenOrigin('https://chat.datameesters.nl')).toBe(true);
	});

	it('accepts localhost ports in dev', () => {
		expect(isAllowedTokenOrigin('http://localhost:5173')).toBe(true);
		expect(isAllowedTokenOrigin('http://localhost:3000')).toBe(true);
	});

	it('rejects subdomain spoofing attempts', () => {
		// The classic trap: `evil-datameesters.nl.attacker.com` looks like
		// `*.datameesters.nl` to a glob but is actually a different host.
		expect(isAllowedTokenOrigin('https://datameesters.nl.attacker.com')).toBe(false);
		expect(isAllowedTokenOrigin('https://evil-datameesters.nl')).toBe(false);
	});

	it('rejects other Ruimtemeesters origins not on the token allowlist', () => {
		// project-specific origins that aren't supposed to push tokens
		expect(isAllowedTokenOrigin('https://nieuwsbrief.datameesters.nl')).toBe(false);
		expect(isAllowedTokenOrigin('https://openwebui.com')).toBe(false);
	});

	it('rejects unrelated origins', () => {
		expect(isAllowedTokenOrigin('https://example.com')).toBe(false);
		expect(isAllowedTokenOrigin('')).toBe(false);
		expect(isAllowedTokenOrigin('null')).toBe(false);
	});
});

describe('parseClerkTokenMessage', () => {
	it('accepts a well-formed payload', () => {
		const parsed = parseClerkTokenMessage({ type: 'rm:clerk-token', token: 'eyJhbGc...' });
		expect(parsed).toEqual({ type: 'rm:clerk-token', token: 'eyJhbGc...' });
	});

	it('rejects payloads with the wrong type field', () => {
		expect(parseClerkTokenMessage({ type: 'rm:other', token: 't' })).toBeNull();
		expect(parseClerkTokenMessage({ type: 'rm:clerk-token-cleared' })).toBeNull();
	});

	it('rejects payloads with a missing or empty token', () => {
		expect(parseClerkTokenMessage({ type: 'rm:clerk-token' })).toBeNull();
		expect(parseClerkTokenMessage({ type: 'rm:clerk-token', token: '' })).toBeNull();
		expect(parseClerkTokenMessage({ type: 'rm:clerk-token', token: null })).toBeNull();
		expect(parseClerkTokenMessage({ type: 'rm:clerk-token', token: 123 })).toBeNull();
	});

	it('rejects non-object inputs', () => {
		expect(parseClerkTokenMessage(null)).toBeNull();
		expect(parseClerkTokenMessage(undefined)).toBeNull();
		expect(parseClerkTokenMessage('eyJhbGc...')).toBeNull();
		expect(parseClerkTokenMessage([{ type: 'rm:clerk-token', token: 'x' }])).toBeNull();
	});
});

describe('parseClerkTokenClearedMessage', () => {
	it('accepts the cleared signal', () => {
		expect(parseClerkTokenClearedMessage({ type: 'rm:clerk-token-cleared' })).toEqual({
			type: 'rm:clerk-token-cleared'
		});
	});

	it('rejects unrelated payloads', () => {
		expect(parseClerkTokenClearedMessage({ type: 'rm:clerk-token', token: 'x' })).toBeNull();
		expect(parseClerkTokenClearedMessage(null)).toBeNull();
	});
});

describe('sendChatbotReady', () => {
	// vitest runs in node by default (no jsdom). Stub `globalThis.window`
	// manually so the "in iframe" code path can run without a DOM env.
	let postMessageSpy: ReturnType<typeof vi.fn>;
	const hadWindow = 'window' in globalThis;
	const originalWindow = hadWindow ? (globalThis as any).window : undefined;

	beforeEach(() => {
		postMessageSpy = vi.fn();
		const parentStub = { postMessage: postMessageSpy };
		(globalThis as any).window = {
			parent: parentStub
		};
	});

	afterEach(() => {
		if (hadWindow) {
			(globalThis as any).window = originalWindow;
		} else {
			delete (globalThis as any).window;
		}
	});

	it('posts the typed message to an allowed parent origin', () => {
		const ok = sendChatbotReady('https://geoportaal.datameesters.nl', '0.6.20');
		expect(ok).toBe(true);
		expect(postMessageSpy).toHaveBeenCalledTimes(1);
		const [payload, targetOrigin] = postMessageSpy.mock.calls[0];
		expect(targetOrigin).toBe('https://geoportaal.datameesters.nl');
		expect(payload).toEqual({
			type: 'rm:chatbot-ready',
			iframeVersion: '0.6.20',
			protocolVersion: CLERK_TOKEN_PROTOCOL_VERSION
		});
	});

	it('refuses to post to a non-allowlisted origin', () => {
		const ok = sendChatbotReady('https://example.com', '0.6.20');
		expect(ok).toBe(false);
		expect(postMessageSpy).not.toHaveBeenCalled();
	});

	it('refuses to broadcast — never uses *', () => {
		// Belt-and-braces: an empty origin string is not allowlisted and
		// must not produce a wildcard fallback.
		expect(sendChatbotReady('', '0.6.20')).toBe(false);
		expect(postMessageSpy).not.toHaveBeenCalled();
	});

	it('refuses to post when not in an iframe (parent === self)', () => {
		// Top-level page: window.parent === window. The helper must not
		// post to itself.
		const selfRef: any = {};
		selfRef.parent = selfRef;
		(globalThis as any).window = selfRef;
		const ok = sendChatbotReady('https://geoportaal.datameesters.nl', '0.6.20');
		expect(ok).toBe(false);
	});
});

describe('getAllowedTokenOrigins', () => {
	it('returns a non-empty allowlist including the canonical chat origin', () => {
		const origins = getAllowedTokenOrigins();
		expect(origins.length).toBeGreaterThan(0);
		expect(origins).toContain('https://chat.datameesters.nl');
		expect(origins).toContain('https://geoportaal.datameesters.nl');
	});
});
