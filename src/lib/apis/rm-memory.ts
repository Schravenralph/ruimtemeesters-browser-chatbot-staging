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
