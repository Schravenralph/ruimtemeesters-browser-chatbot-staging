import { WEBUI_API_BASE_URL } from '$lib/constants';

/**
 * Mirror of `ActiveProject` Pydantic model in
 * `backend/open_webui/routers/rm_memory.py` and of `getActiveProject`'s
 * row shape in `Ruimtemeesters-Memory/src/services/getActiveProject.ts`.
 */
export interface ActiveProject {
	project_id: string;
	kind: 'bopa' | 'beleidsscan' | 'onderbouwing' | 'custom' | string;
	label?: string | null;
	set_at: string;
}

export type MemoryScope = 'user' | 'project' | 'global';
export type MemoryType = 'user' | 'feedback' | 'project' | 'reference' | 'session-summary';

/**
 * Mirror of `MemoryEntry` (index view) in the BFF — name + description
 * + metadata, no content. Use {@link getMemoryEntry} for the body.
 */
export interface MemoryEntry {
	name: string;
	type: MemoryType | string;
	scope: MemoryScope | string;
	description: string;
	owner_user_id: string;
	project_id: string | null;
	updated_at: string;
}

export interface MemoryDetail extends MemoryEntry {
	id: string;
	content: string;
	created_at: string;
}

export interface ListMemoriesOutput {
	entries: MemoryEntry[];
}

export interface SaveMemoryInput {
	name: string;
	description: string;
	type: MemoryType;
	content: string;
	scope?: MemoryScope;
	project_id?: string;
}

export interface SaveMemoryOutput {
	id: string;
	name: string;
	type: string;
	scope: string;
	project_id: string | null;
	created: boolean;
	updated: boolean;
}

export interface ForgetMemoryOutput {
	deleted: boolean;
	rows: number;
}

interface ListMemoriesQuery {
	scope?: MemoryScope;
	type?: MemoryType;
	project_id?: string;
	limit?: number;
	[k: string]: unknown;
}

const buildQuery = (params: Record<string, unknown>): string => {
	const sp = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v === undefined || v === null || v === '') continue;
		sp.set(k, String(v));
	}
	const s = sp.toString();
	return s ? `?${s}` : '';
};

/**
 * GET /api/v1/rm-memory/active-project?chat_id=<id> — return the project
 * currently bound to (caller, chat), or `null` when the chat has no
 * active project. Throws only on transport / parse failures; a clean
 * 200 + `null` body is a normal "no project bound" signal.
 *
 * The chat_id flows through to the memory service as `X-Thread-Id`.
 */
export const getActiveProject = async (
	token: string,
	chatId: string
): Promise<ActiveProject | null> => {
	if (!chatId) return null;

	let error: { detail?: string } | string | null = null;
	let caught = false;
	let result: ActiveProject | null = null;

	const url = `${WEBUI_API_BASE_URL}/rm-memory/active-project?chat_id=${encodeURIComponent(chatId)}`;

	try {
		const res = await fetch(url, {
			method: 'GET',
			headers: {
				Accept: 'application/json',
				Authorization: `Bearer ${token}`
			}
		});
		if (!res.ok) {
			caught = true;
			error = (await res.json().catch(() => null)) ?? `HTTP ${res.status}`;
		} else {
			// 200 body is either an ActiveProject object or `null`.
			result = await res.json();
		}
	} catch (err) {
		caught = true;
		error = err instanceof Error ? err.message : String(err);
	}

	if (caught) {
		// Pill is a soft-fail surface — log + return null so the navbar
		// doesn't break if the BFF is offline. Mirrors the fail-open
		// behaviour of the rm-memory inlet filters.
		console.warn('getActiveProject failed:', error);
		return null;
	}

	return result;
};

/**
 * GET /api/v1/rm-memory — list the caller's memory entries (user +
 * project + global visible to them). Returns the index view (no body).
 */
export const listMemories = async (
	token: string,
	query: ListMemoriesQuery = {}
): Promise<ListMemoriesOutput> => {
	const url = `${WEBUI_API_BASE_URL}/rm-memory${buildQuery(query)}`;
	const res = await fetch(url, {
		method: 'GET',
		headers: { Accept: 'application/json', Authorization: `Bearer ${token}` }
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw body?.detail ?? `HTTP ${res.status}`;
	}
	return res.json();
};

/**
 * GET /api/v1/rm-memory/{name} — fetch one entry with full content.
 */
export const getMemoryEntry = async (
	token: string,
	name: string,
	opts: { type?: MemoryType; project_id?: string } = {}
): Promise<MemoryDetail> => {
	const url = `${WEBUI_API_BASE_URL}/rm-memory/${encodeURIComponent(name)}${buildQuery(opts)}`;
	const res = await fetch(url, {
		method: 'GET',
		headers: { Accept: 'application/json', Authorization: `Bearer ${token}` }
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw body?.detail ?? `HTTP ${res.status}`;
	}
	return res.json();
};

/**
 * POST /api/v1/rm-memory — upsert a memory entry. Re-saving with the
 * same (scope, project, type, name) overwrites; new tuples insert.
 */
export const saveMemoryEntry = async (
	token: string,
	body: SaveMemoryInput
): Promise<SaveMemoryOutput> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/rm-memory`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(body)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw body?.detail ?? `HTTP ${res.status}`;
	}
	return res.json();
};

/**
 * DELETE /api/v1/rm-memory/{name} — hard-delete one of the caller's
 * entries. The MCP returns `{deleted, rows}`; `rows == 0` means no
 * matching entry, which the BFF surfaces as 200 (not 404).
 */
export const forgetMemoryEntry = async (
	token: string,
	name: string,
	opts: { type?: MemoryType; scope?: MemoryScope; project_id?: string } = {}
): Promise<ForgetMemoryOutput> => {
	const url = `${WEBUI_API_BASE_URL}/rm-memory/${encodeURIComponent(name)}${buildQuery(opts)}`;
	const res = await fetch(url, {
		method: 'DELETE',
		headers: { Accept: 'application/json', Authorization: `Bearer ${token}` }
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw body?.detail ?? `HTTP ${res.status}`;
	}
	return res.json();
};
