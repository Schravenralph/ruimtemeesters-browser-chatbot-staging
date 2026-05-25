// Slash-action registry (WI-015).
//
// Slash *actions* are entries in the `/` autocomplete dropdown that
// *do something* on select, instead of inserting prompt text. They
// share the `/` trigger with the existing Prompts list (rendered above
// it by Commands/Slash.svelte) but are routed through a separate
// callback path so the two contracts stay distinct:
//
//   - Prompt  → insertText(promptBody)        (existing /-handler)
//   - Action  → action.run(actionContext)     (this module)
//
// Adding a new slash action is appending one entry to `slashActions`.
// The registry is small + static on purpose — when it grows past a
// dozen we'll revisit (dynamic load from skills API, permission gating,
// etc.). For v0 it ships with `document` only.

import type { Writable } from 'svelte/store';
import type { i18n as i18nType } from 'i18next';

import { openDocGenPanelForCurrentChat } from '$lib/integrations/docGen/panelLifecycle';

/**
 * Context the registry hands to each action's `run`. Currently just
 * i18n (for translated toasts), but kept as an object so additions
 * don't force a signature break on every existing action.
 */
export interface SlashActionContext {
	/** The OWUI i18next store, pulled from Svelte context by the caller. */
	i18n: Writable<i18nType>;
}

/**
 * Minimal user shape the registry needs for permission gating. Avoids a
 * hard dependency on `$lib/stores`'s SessionUser (which is `any` on
 * `.permissions` anyway) so this module stays test-friendly.
 */
export interface SlashActionUser {
	role?: string;
	permissions?: { chat?: { controls?: boolean } } & Record<string, unknown>;
}

export interface SlashAction {
	/** Lowercase id; also the typed command without the slash (`document` → `/document`). */
	id: string;
	/** Human-readable label, Dutch. */
	label: string;
	/** Subtitle shown under the label in the dropdown. */
	description: string;
	/** Optional emoji/glyph for the dropdown item. */
	icon?: string;
	/**
	 * Optional visibility predicate. Returns true when the action should
	 * appear in the dropdown for this user. Bugbot PR #132 finding: without
	 * this, `/document` lets a user denied `chat.controls` open the panel
	 * the toolbar button hides from them.
	 */
	gate?: (user: SlashActionUser | null | undefined) => boolean;
	/** Side-effect to execute on select. May be async; return value is ignored. */
	run: (ctx: SlashActionContext) => void | Promise<void>;
}

/**
 * Document action mirrors `DocGenToggleButton.svelte`'s visibility check:
 * admins always see it; everyone else sees it unless `chat.controls` is
 * explicitly set to `false` (default permissive when the field is
 * missing). Exported for direct unit test.
 */
export function documentActionGate(user: SlashActionUser | null | undefined): boolean {
	if (!user) return true; // pre-load: defer to the toolbar's own guard.
	if (user.role === 'admin') return true;
	return user.permissions?.chat?.controls ?? true;
}

export const slashActions: SlashAction[] = [
	{
		id: 'document',
		label: 'Document',
		description: 'Open de DocGen-zijbalk voor deze chat',
		icon: '📄',
		gate: documentActionGate,
		run: ({ i18n }) => {
			void openDocGenPanelForCurrentChat({ i18n });
		}
	}
];

/**
 * Filter the registry by a typed query (the text after `/`) and the
 * current user (for permission gating). Match is case-insensitive
 * against id and label. Empty query returns all visible actions.
 */
export function filterSlashActions(
	query: string,
	user: SlashActionUser | null | undefined = null
): SlashAction[] {
	const visible = slashActions.filter((a) => !a.gate || a.gate(user));
	const q = query.trim().toLowerCase();
	if (!q) return visible;
	return visible.filter(
		(a) => a.id.toLowerCase().includes(q) || a.label.toLowerCase().includes(q)
	);
}
