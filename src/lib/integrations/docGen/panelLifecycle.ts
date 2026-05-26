// Shared "open the DocGen panel for the current chat" lifecycle (WI-015).
//
// Extracted from DocGenToggleButton.svelte so the same flow is reusable
// from the `/document` slash command (and any future entry point —
// command palette, BOPA-skill auto-open, etc.). All caveats that lived
// inline in the toggle button (chat-id race, temp-chat guard, mint
// failure handling, iframe-mount polling) live here now; the toggle
// button delegates to this function and only owns its own UI state
// (busy flag, chat-change effect, button styling).

import { tick } from 'svelte';
import { get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import type { i18n as i18nType } from 'i18next';
import { toast } from 'svelte-sonner';

import {
	chatId as chatIdStore,
	embed,
	showControls,
	showEmbeds,
	type EmbedDescriptor
} from '$lib/stores';
import { getOrMintDocIdForChat } from './chatMeta';
import { docGenPanelState, openDocGenIframe } from './store';

export interface OpenDocGenPanelOptions {
	i18n: Writable<i18nType>;
	/** Override the default `https://doc-gen.datameesters.nl` base. */
	iframeBase?: string;
}

export type OpenDocGenPanelResult =
	| { ok: true; docId: string; reopened?: boolean }
	| {
			ok: false;
			reason: 'no-chat' | 'temp-chat' | 'mint-failed' | 'iframe-mount-failed' | 'chat-switched';
	  };

export const DOCGEN_IFRAME_BASE =
	(import.meta.env?.VITE_RMDG_IFRAME_BASE as string | undefined) ||
	'https://doc-gen.datameesters.nl';

const DEFAULT_IFRAME_BASE = DOCGEN_IFRAME_BASE;

/**
 * Guard for the toggle button's "embed-rail desync" $effect: returns true
 * when the active `embed` descriptor is our DG iframe (and not, e.g.,
 * Citations replacing it). Mirrors the prefix check used in the helper.
 */
export function embedIsDocGenIframe(e: EmbedDescriptor | null): boolean {
	return (
		e !== null &&
		e?.trusted === true &&
		typeof e?.url === 'string' &&
		e.url.startsWith(DOCGEN_IFRAME_BASE)
	);
}

/**
 * Open the DG iframe side-panel for the active chat. Idempotent: if the
 * panel is already open it's a no-op (returns `reopened: true`).
 *
 * All user-facing errors are toasted inside the helper; the return value
 * is for callers that want to react programmatically (e.g. analytics).
 */
export async function openDocGenPanelForCurrentChat(
	opts: OpenDocGenPanelOptions
): Promise<OpenDocGenPanelResult> {
	const { i18n } = opts;
	const t = get(i18n).t.bind(get(i18n));
	const iframeBase = opts.iframeBase ?? DEFAULT_IFRAME_BASE;
	const iframeOrigin = (() => {
		try {
			return new URL(iframeBase).origin;
		} catch {
			return DEFAULT_IFRAME_BASE;
		}
	})();

	const panel = get(docGenPanelState);
	if (panel.open && panel.docId) {
		return { ok: true, docId: panel.docId, reopened: true };
	}

	const initialChatId = get(chatIdStore);
	if (!initialChatId) {
		toast.error(t('Start een chat voordat je een document opent.'));
		return { ok: false, reason: 'no-chat' };
	}
	// Temp-chat ids (`local:` prefix) aren't persisted server-side, so we
	// can't bind a docId to them via chat.meta. Same guard as the toggle
	// button (WI-014 Bugbot MEDIUM on 91851a09).
	if (initialChatId.startsWith('local:')) {
		toast.error(t('Documenten zijn niet beschikbaar in tijdelijke chats. Start een gewone chat.'));
		return { ok: false, reason: 'temp-chat' };
	}

	const stillSameChat = () => get(chatIdStore) === initialChatId;

	let docId: string;
	try {
		docId = await getOrMintDocIdForChat(localStorage.token, initialChatId, iframeBase);
	} catch (err) {
		console.error('docGen: failed to read/mint docId for chat', err);
		toast.error(t('Kon de document-id voor deze chat niet ophalen.'));
		return { ok: false, reason: 'mint-failed' };
	}
	if (!stillSameChat()) return { ok: false, reason: 'chat-switched' };

	const url = `${iframeBase}/iframe-embed.html?docId=${encodeURIComponent(docId)}`;
	const descriptor: EmbedDescriptor = { url, title: 'Document', trusted: true };
	embed.set(descriptor as unknown as null);
	await showControls.set(true);
	await showEmbeds.set(true);
	if (!stillSameChat()) {
		showEmbeds.set(false);
		embed.set(null);
		return { ok: false, reason: 'chat-switched' };
	}

	const iframeEl = await waitForEmbedIframe();
	if (!stillSameChat()) {
		showEmbeds.set(false);
		embed.set(null);
		return { ok: false, reason: 'chat-switched' };
	}
	if (!iframeEl) {
		toast.error(t('Document-paneel kon niet worden gestart.'));
		console.error('docGen: iframe element not found after panel open');
		showEmbeds.set(false);
		embed.set(null);
		return { ok: false, reason: 'iframe-mount-failed' };
	}

	openDocGenIframe({ iframe: iframeEl, docId, iframeOrigin });
	return { ok: true, docId };
}

async function waitForEmbedIframe(
	maxWaitMs = 2000,
	intervalMs = 50
): Promise<HTMLIFrameElement | null> {
	const deadline = Date.now() + maxWaitMs;
	while (Date.now() < deadline) {
		await tick();
		const el = findEmbedIframe();
		if (el) return el;
		await new Promise((r) => setTimeout(r, intervalMs));
	}
	return null;
}

function findEmbedIframe(): HTMLIFrameElement | null {
	return document.querySelector<HTMLIFrameElement>(
		'.docgen-embeds-pane iframe, [data-rmdg-embed-host] iframe, iframe[src*="iframe-embed.html"]'
	);
}
