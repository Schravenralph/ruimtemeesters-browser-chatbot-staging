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

import { documentActionGate, filterSlashActions, slashActions } from './registry';
import type { SlashActionContext, SlashActionUser } from './registry';

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

describe('documentActionGate (Bugbot PR #132 fix)', () => {
	it('denies when user is null (deny-by-default during init load)', () => {
		// Returning true here would let a non-admin briefly invoke the
		// action via `/` while $user is still null on first render —
		// openDocGenPanelForCurrentChat does not re-check user role
		// downstream. Bugbot MED follow-up on PR #134.
		expect(documentActionGate(null)).toBe(false);
		expect(documentActionGate(undefined)).toBe(false);
	});

	it('admits admins regardless of permissions', () => {
		const admin: SlashActionUser = {
			role: 'admin',
			permissions: { chat: { controls: false } }
		};
		expect(documentActionGate(admin)).toBe(true);
	});

	it('admits non-admins by default (permissive when permission missing)', () => {
		expect(documentActionGate({ role: 'user' })).toBe(true);
		expect(documentActionGate({ role: 'user', permissions: {} })).toBe(true);
		expect(documentActionGate({ role: 'user', permissions: { chat: {} } })).toBe(true);
	});

	it('admits non-admins when chat.controls is explicitly true', () => {
		expect(documentActionGate({ role: 'user', permissions: { chat: { controls: true } } })).toBe(
			true
		);
	});

	it('denies non-admins when chat.controls is explicitly false', () => {
		expect(documentActionGate({ role: 'user', permissions: { chat: { controls: false } } })).toBe(
			false
		);
	});
});

describe('filterSlashActions', () => {
	const adminUser: SlashActionUser = { role: 'admin' };
	const deniedUser: SlashActionUser = {
		role: 'user',
		permissions: { chat: { controls: false } }
	};

	it('returns all entries for an empty query (admin)', () => {
		expect(filterSlashActions('', adminUser).length).toBe(slashActions.length);
		expect(filterSlashActions('   ', adminUser).length).toBe(slashActions.length);
	});

	it('returns no permission-gated entries for null user (deny-by-default during init)', () => {
		// Inverse of the admin case: during the brief init window when
		// `$user` is null, every action with a permission gate is hidden
		// so a non-admin can't briefly trigger one. Admins see the full
		// list as soon as $user resolves.
		const visible = filterSlashActions('');
		expect(visible.some((a) => a.id === 'document')).toBe(false);
	});

	it('hides the document action from users denied chat.controls', () => {
		expect(filterSlashActions('', deniedUser).map((a) => a.id)).not.toContain('document');
		expect(filterSlashActions('doc', deniedUser)).toEqual([]);
	});

	it('matches by id prefix', () => {
		expect(filterSlashActions('doc', adminUser).map((a) => a.id)).toEqual(['document']);
	});

	it('matches by id full', () => {
		expect(filterSlashActions('document', adminUser).map((a) => a.id)).toEqual(['document']);
	});

	it('matches by label (case-insensitive)', () => {
		expect(filterSlashActions('DOCUMENT', adminUser).map((a) => a.id)).toEqual(['document']);
	});

	it('returns empty for non-matching query', () => {
		expect(filterSlashActions('xyzzy', adminUser)).toEqual([]);
	});
});
