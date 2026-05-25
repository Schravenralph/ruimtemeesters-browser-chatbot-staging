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

export interface SlashAction {
	/** Lowercase id; also the typed command without the slash (`document` → `/document`). */
	id: string;
	/** Human-readable label, Dutch. */
	label: string;
	/** Subtitle shown under the label in the dropdown. */
	description: string;
	/** Optional emoji/glyph for the dropdown item. */
	icon?: string;
	/** Side-effect to execute on select. May be async; return value is ignored. */
	run: (ctx: SlashActionContext) => void | Promise<void>;
}

export const slashActions: SlashAction[] = [
	{
		id: 'document',
		label: 'Document',
		description: 'Open de DocGen-zijbalk voor deze chat',
		icon: '📄',
		run: ({ i18n }) => {
			void openDocGenPanelForCurrentChat({ i18n });
		}
	}
];

/**
 * Filter the registry by a typed query (the text after `/`). Match is
 * case-insensitive against id and label. Empty query returns all.
 */
export function filterSlashActions(query: string): SlashAction[] {
	const q = query.trim().toLowerCase();
	if (!q) return slashActions.slice();
	return slashActions.filter(
		(a) => a.id.toLowerCase().includes(q) || a.label.toLowerCase().includes(q)
	);
}
