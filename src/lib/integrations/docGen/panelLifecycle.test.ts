// Tests for embedIsDocGenIframe (WI-015). The open-lifecycle itself is
// covered by manual + e2e (it touches localStorage, fetch, the OWUI
// chats API, and waits for a real iframe DOM — too much surface to
// mock usefully in vitest, and the WI-014 toolbar button has shipped
// the same code path to prod).
//
// Exception: the busy-guard reentry path (issue #137) IS unit-tested
// here, because it kicks in BEFORE any of the expensive async work.
// Setting up a panel-state mock that triggers the idempotent reopen
// early-return is enough to exercise the same-chat reentry case
// without mocking localStorage / fetch / the chats API.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
	__resetInFlightOpenForTesting,
	embedIsDocGenIframe,
	openDocGenPanelForCurrentChat
} from './panelLifecycle';
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

// ─── Busy-guard reentry ────────────────────────────────────────────────
// Double-tapping `/document` (slash) or rapidly clicking the toolbar
// button used to mint two doc-gen rows (POST /documents is non-
// idempotent) and race two iframe mounts. The in-flight slot collapses
// same-chat reentry onto a single promise.

// `vi.hoisted` because the factory below is also hoisted; bare top-level
// `const`s aren't yet initialised when the factory runs.
const mockState = vi.hoisted(() => ({
	chatIdStore: { __mock: 'chatId' } as object,
	docGenPanelStateStore: { __mock: 'panel' } as object,
	chatIdValue: null as string | null,
	panelValue: { open: false, docId: null as string | null, chatId: null as string | null }
}));

vi.mock('svelte/store', async (orig) => {
	const real = (await orig()) as Record<string, unknown>;
	return {
		...real,
		get: vi.fn((store: unknown) => {
			if (store === mockState.chatIdStore) return mockState.chatIdValue;
			if (store === mockState.docGenPanelStateStore) return mockState.panelValue;
			// i18n: return a minimal shape with a `t` method.
			return { t: (k: string) => k };
		})
	};
});

vi.mock('$lib/stores', () => ({
	chatId: mockState.chatIdStore,
	embed: { set: vi.fn() },
	showControls: { set: vi.fn() },
	showEmbeds: { set: vi.fn() }
}));

vi.mock('./store', () => ({
	docGenPanelState: mockState.docGenPanelStateStore,
	openDocGenIframe: vi.fn(),
	disconnectDocGenIframe: vi.fn()
}));

vi.mock('svelte-sonner', () => ({
	toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() }
}));

const dummyI18n = {} as unknown as Parameters<typeof openDocGenPanelForCurrentChat>[0]['i18n'];

describe('openDocGenPanelForCurrentChat — busy guard', () => {
	beforeEach(() => {
		__resetInFlightOpenForTesting();
		mockState.chatIdValue = null;
		mockState.panelValue = { open: false, docId: null, chatId: null };
	});

	it('collapses same-chat reentry onto a single doOpen invocation', async () => {
		// Three concurrent calls for the same chat. Each call settles with
		// the same result (idempotent-reopen early-return), but doOpen's
		// side effects (read panel state) run exactly once — the second
		// and third calls fall straight through the busy guard.
		mockState.chatIdValue = 'chat-A';
		mockState.panelValue = { open: true, docId: 'doc-existing', chatId: 'chat-A' };

		const results = await Promise.all([
			openDocGenPanelForCurrentChat({ i18n: dummyI18n }),
			openDocGenPanelForCurrentChat({ i18n: dummyI18n }),
			openDocGenPanelForCurrentChat({ i18n: dummyI18n })
		]);

		expect(results).toEqual([
			{ ok: true, docId: 'doc-existing', reopened: true },
			{ ok: true, docId: 'doc-existing', reopened: true },
			{ ok: true, docId: 'doc-existing', reopened: true }
		]);
	});

	it('disconnects exactly once when reentry races a cross-chat open', async () => {
		// Different chat is open from a prior session. The first reentry
		// call should disconnect that stale panel; the second concurrent
		// call must NOT disconnect a second time (otherwise a flapping
		// double-tap eats two iframe slots).
		const { disconnectDocGenIframe } = (await import('./store')) as unknown as {
			disconnectDocGenIframe: ReturnType<typeof vi.fn>;
		};
		disconnectDocGenIframe.mockClear();

		mockState.chatIdValue = 'local:temp-chat'; // bails quickly after the disconnect
		mockState.panelValue = { open: true, docId: 'doc-X', chatId: 'chat-stale' };

		await Promise.all([
			openDocGenPanelForCurrentChat({ i18n: dummyI18n }),
			openDocGenPanelForCurrentChat({ i18n: dummyI18n })
		]);

		expect(disconnectDocGenIframe).toHaveBeenCalledTimes(1);
	});

	it('clears the slot after settle so a later click runs fresh', async () => {
		mockState.chatIdValue = 'chat-A';
		mockState.panelValue = { open: true, docId: 'doc-existing', chatId: 'chat-A' };

		await openDocGenPanelForCurrentChat({ i18n: dummyI18n });
		// After settle, the slot is null; a fresh call must not be blocked
		// by stale state. Confirm by re-firing concurrently — both must
		// resolve cleanly.
		const [a, b] = await Promise.all([
			openDocGenPanelForCurrentChat({ i18n: dummyI18n }),
			openDocGenPanelForCurrentChat({ i18n: dummyI18n })
		]);
		expect(a).toEqual({ ok: true, docId: 'doc-existing', reopened: true });
		expect(b).toEqual({ ok: true, docId: 'doc-existing', reopened: true });
	});

	it('short-circuits no-chat without entering the busy slot', async () => {
		mockState.chatIdValue = null;
		const result = await openDocGenPanelForCurrentChat({ i18n: dummyI18n });
		expect(result).toEqual({ ok: false, reason: 'no-chat' });
		// A second call with the same null chat should still be a no-op,
		// not blocked by a stale in-flight slot.
		const second = await openDocGenPanelForCurrentChat({ i18n: dummyI18n });
		expect(second).toEqual({ ok: false, reason: 'no-chat' });
	});
});
