// Helper that returns the tool_servers entry to inject into a chat
// completion request when the DG panel is open (WI-014).
//
// OWUI's middleware (middleware.py:2634) treats `tool_servers` entries
// as direct (browser-executed) tools when they include `specs` and a
// `server` block. The `direct: True` flag is set internally; we just
// hand it the spec array + system prompt + server identifier.

import { docGenToolSpecs, DOC_GEN_SYSTEM_PROMPT, DOC_GEN_VIRTUAL_SERVER_URL } from './tools';

export interface DocGenToolServerEntry {
	url: string;
	name: string;
	specs: typeof docGenToolSpecs;
	system_prompt: string;
}

/**
 * Returns the chatbot's tool_servers contribution when the DG panel is
 * open. Returns null when closed — caller should skip injection in that
 * case.
 */
export function getDocGenToolServerEntry(opts: {
	panelOpen: boolean;
}): DocGenToolServerEntry | null {
	if (!opts.panelOpen) return null;
	return {
		url: DOC_GEN_VIRTUAL_SERVER_URL,
		name: 'docgen',
		specs: docGenToolSpecs,
		system_prompt: DOC_GEN_SYSTEM_PROMPT
	};
}
