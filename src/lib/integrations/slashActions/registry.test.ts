// Tests for the slash-action registry (WI-015). Logic-only — no DOM.

import { describe, expect, it, vi } from 'vitest';

// `vi.hoisted` runs *before* the hoisted `vi.mock` factory, so the spy
// is defined when the factory references it. (Top-level `const` doesn't
// work — see vitest docs on "vi.mock factory hoisting".)
const { openSpy } = vi.hoisted(() => ({
	openSpy: vi.fn(() => Promise.resolve({ ok: true, docId: 'doc-mock' }))
}));
vi.mock('$lib/integrations/docGen/panelLifecycle', () => ({
	openDocGenPanelForCurrentChat: openSpy
}));

import { filterSlashActions, slashActions } from './registry';
import type { SlashActionContext } from './registry';

describe('slashActions registry', () => {
	it('exposes the document action', () => {
		const ids = slashActions.map((a) => a.id);
		expect(ids).toContain('document');
	});

	it('document action has the expected shape', () => {
		const doc = slashActions.find((a) => a.id === 'document');
		expect(doc).toBeDefined();
		expect(doc?.label).toBe('Document');
		expect(typeof doc?.description).toBe('string');
		expect(doc?.description.length).toBeGreaterThan(0);
		expect(typeof doc?.run).toBe('function');
	});

	it('document action calls openDocGenPanelForCurrentChat with i18n context', () => {
		openSpy.mockClear();
		const ctx: SlashActionContext = {
			// Minimal Writable-like stand-in; the helper only uses `get(i18n).t`.
			i18n: { subscribe: () => () => {} } as unknown as SlashActionContext['i18n']
		};
		const doc = slashActions.find((a) => a.id === 'document')!;
		doc.run(ctx);
		expect(openSpy).toHaveBeenCalledTimes(1);
		expect(openSpy).toHaveBeenCalledWith(expect.objectContaining({ i18n: ctx.i18n }));
	});
});

describe('filterSlashActions', () => {
	it('returns all entries for an empty query', () => {
		expect(filterSlashActions('').length).toBe(slashActions.length);
		expect(filterSlashActions('   ').length).toBe(slashActions.length);
	});

	it('matches by id prefix', () => {
		expect(filterSlashActions('doc').map((a) => a.id)).toEqual(['document']);
	});

	it('matches by id full', () => {
		expect(filterSlashActions('document').map((a) => a.id)).toEqual(['document']);
	});

	it('matches by label (case-insensitive)', () => {
		expect(filterSlashActions('DOCUMENT').map((a) => a.id)).toEqual(['document']);
	});

	it('returns empty for non-matching query', () => {
		expect(filterSlashActions('xyzzy')).toEqual([]);
	});
});
