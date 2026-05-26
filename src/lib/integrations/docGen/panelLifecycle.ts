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
import { disconnectDocGenIframe, docGenPanelState, openDocGenIframe } from './store';

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

// In-flight tracking. Two distinct call sites can fire concurrently:
// the toolbar `DocGenToggleButton` (already has its own UI `busy` flag)
// and the `/document` slash action (no flag of its own). A user who
// double-taps Enter on `/document` would otherwise mint two doc-gen
// rows (POST /documents is non-idempotent) and race two iframe mounts
// against each other. Same-chat reentry returns the existing promise;
// different-chat reentry starts fresh (the prior call's
// `stillSameChat()` checks naturally abort it). Issue #137 (MED).
let inFlightOpen: { chatId: string; promise: Promise<OpenDocGenPanelResult> } | null = null;

/** Test seam — clear the in-flight slot between cases. Production
 *  callers don't use this; the slot self-clears on settle. */
export function __resetInFlightOpenForTesting(): void {
	inFlightOpen = null;
}

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
	// Validate the iframe base once. If a caller (or VITE_RMDG_IFRAME_BASE)
	// hands us a malformed URL, fall back BOTH the iframeBase and the
	// derived iframeOrigin together — the previous code only swapped the
	// origin and then used the malformed string when building the iframe
	// URL, so the iframe would 404 instead of recovering. The default is
	// a well-formed URL, so this never throws on the fallback path.
	const { iframeBase, iframeOrigin } = (() => {
		const candidate = opts.iframeBase ?? DEFAULT_IFRAME_BASE;
		try {
			return { iframeBase: candidate, iframeOrigin: new URL(candidate).origin };
		} catch {
			return {
				iframeBase: DEFAULT_IFRAME_BASE,
				iframeOrigin: new URL(DEFAULT_IFRAME_BASE).origin
			};
		}
	})();

	const initialChatId = get(chatIdStore);
	if (!initialChatId) {
		toast.error(t('Start een chat voordat je een document opent.'));
		return { ok: false, reason: 'no-chat' };
	}

	// Busy guard: a reentrant call for the SAME chat reuses the existing
	// promise instead of firing a second POST /documents + iframe mount.
	// Reentry from a DIFFERENT chat is allowed to start fresh; the prior
	// call's `stillSameChat()` checks will abort it the next time it hits
	// an await boundary. Issue #137.
	if (inFlightOpen?.chatId === initialChatId) {
		return inFlightOpen.promise;
	}

	const work = doOpen({ initialChatId, iframeBase, iframeOrigin, t });
	inFlightOpen = { chatId: initialChatId, promise: work };
	try {
		return await work;
	} finally {
		if (inFlightOpen?.promise === work) inFlightOpen = null;
	}
}

async function doOpen(args: {
	initialChatId: string;
	iframeBase: string;
	iframeOrigin: string;
	t: (k: string) => string;
}): Promise<OpenDocGenPanelResult> {
	const { initialChatId, iframeBase, iframeOrigin, t } = args;

	// Idempotent reopen: only short-circuit when the still-open panel
	// belongs to the SAME chat as the click. Without the chat-id check,
	// "open doc in chat A → switch to chat B → click open doc" returned
	// chat A's docId for chat B (Bugbot HIGH on 875106c follow-up).
	const panel = get(docGenPanelState);
	if (panel.open && panel.docId && panel.chatId === initialChatId) {
		return { ok: true, docId: panel.docId, reopened: true };
	}
	if (panel.open) {
		disconnectDocGenIframe();
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

	openDocGenIframe({ iframe: iframeEl, docId, chatId: initialChatId, iframeOrigin });
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
