// Active iframe-client singleton + helpers (WI-014).
//
// The chatbot has at most one DG iframe panel open at any time (it's
// global to the right-rail Embeds slot). When the panel opens we
// connect an iframe client and stash it here. When it closes we
// disconnect. The `executeTool` socket handler in +layout.svelte looks
// up the active client from this module.
//
// Plain module state + a Svelte writable for reactive UI subscribers
// (the toolbar toggle button reads "is doc panel open").

import { writable, type Writable } from 'svelte/store';
import { connectDocGenIframe, type DocGenIframeClient } from './iframeClient';
import { DOC_GEN_VIRTUAL_SERVER_URL } from './tools';

// ─── Active-client singleton (non-reactive — for socket handlers) ───────

let activeClient: DocGenIframeClient | null = null;

export function getActiveDocGenClient(): DocGenIframeClient | null {
	return activeClient;
}

// ─── Reactive open-state (for UI subscribers) ───────────────────────────

export interface DocGenPanelState {
	open: boolean;
	/** docId currently mounted in the iframe. Null when closed. */
	docId: string | null;
	/** Chat id the panel was opened against. Null when closed. The
	 * panelLifecycle idempotent-reopen path uses this to avoid returning
	 * chat A's doc to a click that came from chat B. */
	chatId: string | null;
}

export const docGenPanelState: Writable<DocGenPanelState> = writable({
	open: false,
	docId: null,
	chatId: null
});

// ─── Lifecycle ──────────────────────────────────────────────────────────

export interface OpenDocGenIframeOptions {
	iframe: HTMLIFrameElement;
	docId: string;
	/** Chat id the panel is being opened against. Tracked alongside the
	 * open state so the idempotent-reopen path in panelLifecycle can
	 * tell whether the still-open panel matches the current chat. */
	chatId: string;
	iframeOrigin?: string;
}

const DEFAULT_IFRAME_ORIGIN = 'https://doc-gen.datameesters.nl';

/**
 * Mount the active client against a freshly-loaded iframe. Disconnects
 * any previous client first (only one active at a time).
 *
 * Returns the new client. The caller doesn't need to keep the reference
 * — `getActiveDocGenClient()` is the access path the socket handler uses.
 */
export function openDocGenIframe(opts: OpenDocGenIframeOptions): DocGenIframeClient {
	disconnectDocGenIframe();
	const client = connectDocGenIframe({
		iframe: opts.iframe,
		iframeOrigin: opts.iframeOrigin ?? DEFAULT_IFRAME_ORIGIN
	});
	activeClient = client;
	docGenPanelState.set({ open: true, docId: opts.docId, chatId: opts.chatId });
	return client;
}

export function disconnectDocGenIframe(): void {
	if (activeClient) {
		activeClient.disconnect();
		activeClient = null;
	}
	docGenPanelState.set({ open: false, docId: null, chatId: null });
}

// ─── Server-URL guard (used by executeTool) ─────────────────────────────

/** True when an OWUI execute:tool event targets the DG virtual server. */
export function isDocGenServerUrl(url: unknown): boolean {
	return typeof url === 'string' && url === DOC_GEN_VIRTUAL_SERVER_URL;
}

// ─── Test seam ──────────────────────────────────────────────────────────
// Tests don't connect a real client — they inject a mock to assert that
// the execute:tool wiring routes correctly. Production code never calls
// this.

export function __setActiveDocGenClientForTesting(client: DocGenIframeClient | null): void {
	activeClient = client;
}
