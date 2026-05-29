/**
 * Thin client for the rm-skills BFF (`/api/v1/rm-skills/*`).
 *
 * Read-only: lists the active persona's mandatory skills (name +
 * description). Skill bodies are deliberately not surfaced here —
 * they're injected server-side by the `skills_context` inlet filter,
 * not consumed by the frontend.
 */

import { WEBUI_API_BASE_URL } from '$lib/constants';

/** Mirror of `ActiveSkill` Pydantic model in
 * `backend/open_webui/routers/rm_skills.py`. */
export interface ActiveSkill {
	name: string;
	description: string;
}

export interface ActiveSkillsOutput {
	persona: string;
	skills: ActiveSkill[];
}

/**
 * GET /api/v1/rm-skills/active?persona=<slug> — list mandatory skills
 * for the active persona. Returns `{persona, skills: []}` when the
 * persona has no mandatory entries; never throws on a 200.
 *
 * Soft-fails on transport errors (returns null) — the chip should
 * disappear rather than break the navbar when rm-skills is offline.
 */
export const getActiveSkills = async (
	token: string,
	persona: string
): Promise<ActiveSkillsOutput | null> => {
	if (!persona) return null;

	const url = `${WEBUI_API_BASE_URL}/rm-skills/active?persona=${encodeURIComponent(persona)}`;

	try {
		const res = await fetch(url, {
			method: 'GET',
			headers: {
				Accept: 'application/json',
				Authorization: `Bearer ${token}`
			}
		});
		if (!res.ok) {
			console.warn('getActiveSkills:', res.status, await res.text().catch(() => ''));
			return null;
		}
		return await res.json();
	} catch (err) {
		console.warn('getActiveSkills transport error:', err);
		return null;
	}
};
