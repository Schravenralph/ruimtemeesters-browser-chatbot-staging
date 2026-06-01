import { describe, expect, it, beforeEach } from 'vitest';
import { get } from 'svelte/store';

import {
	bearerToken,
	clearBearerToken,
	getBearerToken,
	hasBearerToken,
	setBearerToken
} from './clerkBridge';

describe('clerkBridge store', () => {
	beforeEach(() => {
		clearBearerToken();
	});

	it('starts empty', () => {
		expect(getBearerToken()).toBeNull();
		expect(hasBearerToken()).toBe(false);
		expect(get(bearerToken)).toBeNull();
	});

	it('setBearerToken updates both the module-level read and the store', () => {
		setBearerToken('eyJhbGc.payload.sig');
		expect(getBearerToken()).toBe('eyJhbGc.payload.sig');
		expect(hasBearerToken()).toBe(true);
		expect(get(bearerToken)).toBe('eyJhbGc.payload.sig');
	});

	it('clearBearerToken resets both views', () => {
		setBearerToken('eyJ...');
		clearBearerToken();
		expect(getBearerToken()).toBeNull();
		expect(hasBearerToken()).toBe(false);
		expect(get(bearerToken)).toBeNull();
	});

	it('replaces the token in place rather than queueing', () => {
		// The parent refreshes Clerk sessions periodically; the iframe
		// must drop the old token outright and use the new one on the
		// next request — never carry both.
		setBearerToken('first');
		setBearerToken('second');
		expect(getBearerToken()).toBe('second');
		expect(get(bearerToken)).toBe('second');
	});
});
