// chat.meta.docgen.docId — server-side per-chat document binding (WI-014).
//
// Ralph's call (2026-05-22 Q1): persist the chat→doc binding server-side
// from day 1, not localStorage. OWUI's chat record has a free-form
// `meta` JSON field; we use a `docgen` namespace inside it:
//
//     chat.meta.docgen = { docId: "<uuid>" }
//
// First open in a chat mints + persists. Subsequent opens read back the
// same id. Works across browsers (chat lives on the server) and is
// trivial to extend with more docgen state if needed.
//
// API: a single helper. Caller is Chat.svelte / the toolbar-button
// handler, which already has the chat id + the OWUI token in context.

import { getChatById, updateChatById } from '$lib/apis/chats';

interface DocGenChatMeta {
	docId?: string;
}

interface ChatMeta {
	docgen?: DocGenChatMeta;
	[key: string]: unknown;
}

interface ChatShape {
	id?: string;
	chat?: {
		meta?: ChatMeta;
		[key: string]: unknown;
	};
	meta?: ChatMeta;
	[key: string]: unknown;
}

/**
 * Read the docId for this chat. Mints + persists if absent.
 *
 * Returns the docId. Throws on a real backend failure — the caller
 * should toast and bail rather than silently opening a stranger doc.
 *
 * The chat object's shape varies (OWUI returns `{id, chat: {...}}` from
 * /chats/{id}, but the inner `chat` is the persistable blob); we handle
 * both wrappings.
 */
export async function getOrMintDocIdForChat(token: string, chatId: string): Promise<string> {
	const existing = await readDocIdFromChat(token, chatId);
	if (existing) return existing;
	return mintAndPersistDocId(token, chatId);
}

async function readDocIdFromChat(token: string, chatId: string): Promise<string | null> {
	const raw = (await getChatById(token, chatId)) as ChatShape | null;
	if (!raw) return null;
	const meta = raw.chat?.meta ?? raw.meta;
	const docId = meta?.docgen?.docId;
	return typeof docId === 'string' && docId.length > 0 ? docId : null;
}

async function mintAndPersistDocId(token: string, chatId: string): Promise<string> {
	const docId = mintUuid();
	const raw = (await getChatById(token, chatId)) as ChatShape | null;
	// Bugbot HIGH on 289a61f7: if getChatById returns null/empty, the
	// previous code built `inner = {}` and POSTed it back. updateChatById
	// re-wraps as `{chat: {}}` which can REPLACE the persisted chat blob,
	// dropping the entire message history. Fail safe: if we can't read
	// back a chat, refuse to mint — the caller toasts and aborts the open.
	const inner = raw?.chat ?? (raw as Record<string, unknown> | null);
	if (!inner || typeof inner !== 'object' || Object.keys(inner).length === 0) {
		throw new Error(
			`docGen chatMeta: cannot mint docId — getChatById returned no chat for '${chatId}'`
		);
	}
	// The /chats/{id} POST endpoint wraps the chat blob under `chat`.
	// `updateChatById` re-wraps it the same way (chats/index.ts:967). We
	// hand it the inner chat object with a merged meta.docgen.docId.
	const meta: ChatMeta = {
		...((inner as ChatShape).meta ?? {}),
		docgen: {
			...(((inner as ChatShape).meta?.docgen as DocGenChatMeta) ?? {}),
			docId
		}
	};
	const updated = { ...(inner as object), meta };
	await updateChatById(token, chatId, updated);
	return docId;
}

function mintUuid(): string {
	const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
	if (c?.randomUUID) return c.randomUUID();
	// Fallback — should never hit in modern browsers. Belt-and-suspenders.
	const rand = Math.random().toString(36).slice(2);
	return `${Date.now().toString(36)}-${rand}`;
}
