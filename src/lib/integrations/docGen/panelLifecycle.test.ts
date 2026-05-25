// Tests for embedIsDocGenIframe (WI-015). The open-lifecycle itself is
// covered by manual + e2e (it touches localStorage, fetch, the OWUI
// chats API, and waits for a real iframe DOM — too much surface to
// mock usefully in vitest, and the WI-014 toolbar button has shipped
// the same code path to prod).

import { describe, expect, it } from 'vitest';

import { embedIsDocGenIframe } from './panelLifecycle';
import type { EmbedDescriptor } from '$lib/stores';

const ourUrl = 'https://doc-gen.datameesters.nl/iframe-embed.html?docId=abc';

describe('embedIsDocGenIframe', () => {
	it('returns true for the DG iframe descriptor', () => {
		const e: EmbedDescriptor = { url: ourUrl, title: 'Document', trusted: true };
		expect(embedIsDocGenIframe(e)).toBe(true);
	});

	it('returns false for null', () => {
		expect(embedIsDocGenIframe(null)).toBe(false);
	});

	it('returns false for an untrusted descriptor', () => {
		expect(
			embedIsDocGenIframe({ url: ourUrl, title: 'Document', trusted: false } as EmbedDescriptor)
		).toBe(false);
	});

	it('returns false when the url is on a different origin', () => {
		expect(
			embedIsDocGenIframe({
				url: 'https://citations.datameesters.nl/foo',
				title: 'Citation',
				trusted: true
			} as EmbedDescriptor)
		).toBe(false);
	});

	it('returns false when url is missing', () => {
		expect(embedIsDocGenIframe({ title: 'x', trusted: true } as EmbedDescriptor)).toBe(false);
	});
});
