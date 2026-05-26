// Tests for chat.meta.docgen.docId — the chat→doc-gen binding flow.
//
// What this covers:
// - First open: POSTs to doc-gen /documents, persists the returned id
//   on the chat blob, does NOT mint a UUID client-side.
// - Subsequent open: returns the persisted id when doc-gen confirms it.
// - Self-heal: when doc-gen 404s the persisted id, re-mints a fresh one.
// - Failure boundaries: no JWT, doc-gen error, missing id, empty chat
//   blob (history-preservation guard from Bugbot HIGH on 289a61f7).

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getOrMintDocIdForChat } from './chatMeta';

vi.mock('$lib/apis/chats', () => ({
	getChatById: vi.fn(),
	updateChatById: vi.fn()
}));

vi.mock('$lib/integrations/docGenAuth', () => ({
	getDocGenAuthToken: vi.fn()
}));

import { getChatById, updateChatById } from '$lib/apis/chats';
import { getDocGenAuthToken } from '$lib/integrations/docGenAuth';

const API_BASE = 'https://doc-gen.test';

beforeEach(() => {
	vi.mocked(getChatById).mockReset();
	vi.mocked(updateChatById).mockReset();
	vi.mocked(getDocGenAuthToken).mockReset();
	vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
	vi.unstubAllGlobals();
});

function okResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

function errorResponse(status: number, body = ''): Response {
	return new Response(body, { status });
}

describe('getOrMintDocIdForChat', () => {
	it('returns the persisted id when doc-gen confirms it exists', async () => {
		vi.mocked(getChatById).mockResolvedValue({
			id: 'chat-1',
			chat: { title: 'Hello', meta: { docgen: { docId: 'doc-existing' } } }
		});
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');
		vi.mocked(global.fetch).mockResolvedValueOnce(okResponse({ id: 'doc-existing' }));

		const id = await getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE);

		expect(id).toBe('doc-existing');
		expect(global.fetch).toHaveBeenCalledTimes(1);
		const [url, init] = vi.mocked(global.fetch).mock.calls[0];
		expect(url).toBe(`${API_BASE}/documents/doc-existing`);
		expect((init as RequestInit).method).toBeUndefined(); // GET probe
		expect(updateChatById).not.toHaveBeenCalled();
	});

	it('re-mints when doc-gen 404s the persisted id (self-heal)', async () => {
		vi.mocked(getChatById).mockResolvedValue({
			id: 'chat-1',
			chat: { title: 'Hello', meta: { docgen: { docId: 'doc-orphan' } } }
		});
		vi.mocked(updateChatById).mockResolvedValue({});
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');
		vi.mocked(global.fetch)
			.mockResolvedValueOnce(errorResponse(404)) // probe says missing
			.mockResolvedValueOnce(okResponse({ id: 'doc-fresh' }, 201));

		const id = await getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE);

		expect(id).toBe('doc-fresh');
		expect(global.fetch).toHaveBeenCalledTimes(2);
		expect(vi.mocked(global.fetch).mock.calls[1][0]).toBe(`${API_BASE}/documents`);
		const init = vi.mocked(global.fetch).mock.calls[1][1] as RequestInit;
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body as string)).toEqual({ title: 'Hello' });

		expect(updateChatById).toHaveBeenCalledTimes(1);
		const [, , updated] = vi.mocked(updateChatById).mock.calls[0];
		expect((updated as { meta: { docgen: { docId: string } } }).meta.docgen.docId).toBe(
			'doc-fresh'
		);
	});

	it('treats a non-404 probe error as inconclusive and keeps the stored id', async () => {
		vi.mocked(getChatById).mockResolvedValue({
			id: 'chat-1',
			chat: { title: 'Hello', meta: { docgen: { docId: 'doc-existing' } } }
		});
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');
		vi.mocked(global.fetch).mockResolvedValueOnce(errorResponse(500, 'boom'));

		const id = await getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE);

		expect(id).toBe('doc-existing');
		expect(updateChatById).not.toHaveBeenCalled();
	});

	it('treats network error during probe as inconclusive', async () => {
		vi.mocked(getChatById).mockResolvedValue({
			id: 'chat-1',
			chat: { meta: { docgen: { docId: 'doc-existing' } } }
		});
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');
		vi.mocked(global.fetch).mockRejectedValueOnce(new Error('offline'));

		const id = await getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE);

		expect(id).toBe('doc-existing');
		expect(updateChatById).not.toHaveBeenCalled();
	});

	it('mints a fresh doc on first open when no id is persisted', async () => {
		vi.mocked(getChatById).mockResolvedValue({
			id: 'chat-1',
			chat: { title: 'Project Alpha', meta: {} }
		});
		vi.mocked(updateChatById).mockResolvedValue({});
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');
		vi.mocked(global.fetch).mockResolvedValueOnce(okResponse({ id: 'doc-new' }, 201));

		const id = await getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE);

		expect(id).toBe('doc-new');
		expect(global.fetch).toHaveBeenCalledTimes(1);
		expect(vi.mocked(global.fetch).mock.calls[0][0]).toBe(`${API_BASE}/documents`);
		const init = vi.mocked(global.fetch).mock.calls[0][1] as RequestInit;
		expect(JSON.parse(init.body as string)).toEqual({ title: 'Project Alpha' });
		expect((init.headers as Record<string, string>).Authorization).toBe('Bearer jwt-1');

		const [, , updated] = vi.mocked(updateChatById).mock.calls[0];
		expect((updated as { meta: { docgen: { docId: string } } }).meta.docgen.docId).toBe('doc-new');
	});

	it('mints without title when chat has none', async () => {
		vi.mocked(getChatById).mockResolvedValue({ id: 'chat-1', chat: { meta: {} } });
		vi.mocked(updateChatById).mockResolvedValue({});
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');
		vi.mocked(global.fetch).mockResolvedValueOnce(okResponse({ id: 'doc-new' }, 201));

		const id = await getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE);

		expect(id).toBe('doc-new');
		const init = vi.mocked(global.fetch).mock.calls[0][1] as RequestInit;
		expect(JSON.parse(init.body as string)).toEqual({});
	});

	it('throws when Clerk JWT is unavailable at mint time', async () => {
		vi.mocked(getChatById).mockResolvedValue({ id: 'chat-1', chat: { meta: {} } });
		vi.mocked(getDocGenAuthToken).mockResolvedValue(null);

		await expect(getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE)).rejects.toThrow(
			/no Clerk JWT/
		);
		expect(updateChatById).not.toHaveBeenCalled();
	});

	it('throws when doc-gen returns non-2xx on POST', async () => {
		vi.mocked(getChatById).mockResolvedValue({ id: 'chat-1', chat: { meta: {} } });
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');
		vi.mocked(global.fetch).mockResolvedValueOnce(errorResponse(401, 'unauthenticated'));

		await expect(getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE)).rejects.toThrow(
			/HTTP 401/
		);
		expect(updateChatById).not.toHaveBeenCalled();
	});

	it('throws when doc-gen response is missing the id field', async () => {
		vi.mocked(getChatById).mockResolvedValue({ id: 'chat-1', chat: { meta: {} } });
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');
		vi.mocked(global.fetch).mockResolvedValueOnce(okResponse({ workspace_id: 'ws' }, 201));

		await expect(getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE)).rejects.toThrow(
			/response missing id/
		);
	});

	it('refuses to mint when getChatById returns an empty chat (history-loss guard)', async () => {
		// Regression guard: Bugbot HIGH on 289a61f7. updateChatById{chat:{}}
		// can replace the persisted chat blob, dropping message history.
		vi.mocked(getChatById).mockResolvedValue(null);
		vi.mocked(getDocGenAuthToken).mockResolvedValue('jwt-1');

		await expect(getOrMintDocIdForChat('owui-token', 'chat-1', API_BASE)).rejects.toThrow(
			/getChatById returned no chat/
		);
		expect(global.fetch).not.toHaveBeenCalled();
		expect(updateChatById).not.toHaveBeenCalled();
	});
});
