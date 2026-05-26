// chat.meta.docgen.docId — server-side per-chat document binding (WI-014).
//
// Ralph's call (2026-05-22 Q1): persist the chat→doc binding server-side
// from day 1, not localStorage. OWUI's chat record has a free-form
// `meta` JSON field; we use a `docgen` namespace inside it:
//
//     chat.meta.docgen = { docId: "<uuid>" }
//
// First open in a chat creates a real doc-gen row + persists the id.
// Subsequent opens read back the same id (and self-heal if doc-gen no
// longer has the row).
//
// Until 2026-05-26 this helper minted a client-side UUID and persisted
// it WITHOUT telling doc-gen — every first "Open document" click then
// hit a doc-gen 404 because no INSERT ever happened. Now the id we
// store is one doc-gen has actually issued via POST /documents.

import { getChatById, updateChatById } from '$lib/apis/chats';

import { getDocGenAuthToken } from '$lib/integrations/docGenAuth';

interface DocGenChatMeta {
	docId?: string;
}

interface ChatMeta {
	docgen?: DocGenChatMeta;
	[key: string]: unknown;
}

interface ChatShape {
	id?: string;
	title?: string;
	chat?: {
		title?: string;
		meta?: ChatMeta;
		[key: string]: unknown;
	};
	meta?: ChatMeta;
	[key: string]: unknown;
}

const DEFAULT_DOC_GEN_API_BASE = 'https://doc-gen.datameesters.nl';

/**
 * Read the docId for this chat. Mints + persists (against doc-gen) if
 * absent or if the previously-stored id no longer exists in doc-gen.
 *
 * Returns the docId. Throws on a real backend failure — the caller
 * should toast and bail rather than silently opening a stranger doc.
 *
 * The `apiBase` arg exists for tests + future per-env overrides. In
 * production the default points at the public doc-gen host.
 */
export async function getOrMintDocIdForChat(
	token: string,
	chatId: string,
	apiBase: string = DEFAULT_DOC_GEN_API_BASE
): Promise<string> {
	const existing = await readDocIdFromChat(token, chatId);
	if (existing) {
		// Self-heal: 404 on probe = doc-gen never had this row (history
		// of orphaned client-minted UUIDs, or doc-gen DB loss). Anything
		// else (auth blip, 5xx, network) is inconclusive → trust the
		// stored id and let the iframe surface the real error.
		const probe = await probeDocGenDocument(existing, apiBase);
		if (probe !== 'missing') return existing;
	}
	return mintAndPersistDocId(token, chatId, apiBase);
}

async function readDocIdFromChat(token: string, chatId: string): Promise<string | null> {
	const raw = (await getChatById(token, chatId)) as ChatShape | null;
	if (!raw) return null;
	const meta = raw.chat?.meta ?? raw.meta;
	const docId = meta?.docgen?.docId;
	return typeof docId === 'string' && docId.length > 0 ? docId : null;
}

async function mintAndPersistDocId(
	token: string,
	chatId: string,
	apiBase: string
): Promise<string> {
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

	// Seed the doc title from the chat title (if any), so the user sees
	// something meaningful in the doc-gen panel instead of "Untitled".
	const chatTitle = pickTitle(inner) ?? pickTitle(raw);
	const docId = await createDocGenDocument(apiBase, chatTitle);

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
	try {
		await updateChatById(token, chatId, updated);
	} catch (err) {
		await deleteDocGenDocument(apiBase, docId).catch(() => {});
		throw err;
	}
	return docId;
}

function pickTitle(blob: ChatShape | Record<string, unknown> | null): string | undefined {
	const t = (blob as { title?: unknown } | null)?.title;
	return typeof t === 'string' && t.trim().length > 0 ? t.trim() : undefined;
}

/**
 * Create a fresh document in doc-gen and return its id.
 *
 * Auth: Clerk JWT minted via docGenAuth.getDocGenAuthToken(). The
 * doc-gen backend requires `o.id` in the JWT and 401s otherwise;
 * docGenAuth handles active-org selection up front.
 */
async function createDocGenDocument(apiBase: string, title?: string): Promise<string> {
	const jwt = await getDocGenAuthToken();
	if (!jwt) {
		throw new Error('docGen chatMeta: no Clerk JWT available — cannot create doc-gen document');
	}
	const resp = await fetch(`${apiBase}/documents`, {
		method: 'POST',
		headers: {
			Authorization: `Bearer ${jwt}`,
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(title ? { title } : {})
	});
	if (!resp.ok) {
		const body = await resp.text().catch(() => '');
		throw new Error(`docGen POST /documents failed (HTTP ${resp.status}): ${body.slice(0, 200)}`);
	}
	const json = (await resp.json().catch(() => null)) as { id?: unknown } | null;
	const id = json?.id;
	if (typeof id !== 'string' || id.length === 0) {
		throw new Error('docGen POST /documents: response missing id');
	}
	return id;
}

async function deleteDocGenDocument(apiBase: string, docId: string): Promise<void> {
	const jwt = await getDocGenAuthToken();
	if (!jwt) return;
	const resp = await fetch(`${apiBase}/documents/${encodeURIComponent(docId)}`, {
		method: 'DELETE',
		headers: { Authorization: `Bearer ${jwt}` }
	});
	if (!resp.ok && resp.status !== 404) {
		throw new Error(`docGen DELETE /documents/${docId} failed (HTTP ${resp.status})`);
	}
}

type ProbeResult = 'exists' | 'missing' | 'inconclusive';

/**
 * HEAD-style existence probe for a doc-gen document. Returns:
 *  - 'exists' on 2xx
 *  - 'missing' on 404 (the only signal that re-minting is safe)
 *  - 'inconclusive' on anything else (auth blip, 5xx, network) — the
 *    caller should reuse the stored id rather than orphan it.
 *
 * Uses GET because the doc-gen backend doesn't expose HEAD; we ignore
 * the response body. Auth is the same Clerk JWT used for POST.
 */
async function probeDocGenDocument(docId: string, apiBase: string): Promise<ProbeResult> {
	let jwt: string | null = null;
	try {
		jwt = await getDocGenAuthToken();
	} catch {
		return 'inconclusive';
	}
	if (!jwt) return 'inconclusive';
	let resp: Response;
	try {
		resp = await fetch(`${apiBase}/documents/${encodeURIComponent(docId)}`, {
			headers: { Authorization: `Bearer ${jwt}` }
		});
	} catch {
		return 'inconclusive';
	}
	if (resp.status === 404) return 'missing';
	if (resp.ok) return 'exists';
	return 'inconclusive';
}
