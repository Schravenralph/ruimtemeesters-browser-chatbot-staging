<script lang="ts">
	// Toggle button for the Document-Generator iframe panel (WI-014).
	//
	// Owns the open/close lifecycle for the DG panel within a chat:
	//   - On open: mints/reads the chat's docId from chat.meta.docgen,
	//     sets the global embed store to point at iframe-embed.html, marks
	//     it `trusted` (so Embeds.svelte passes allowSameOrigin to the
	//     iframe — DG needs same-origin for Clerk localStorage/cookies),
	//     opens showControls+showEmbeds, waits a tick for the iframe DOM,
	//     queries it, and connects an iframeClient via the docGen store
	//     (the active client becomes available to the execute:tool socket
	//     handler in +layout.svelte).
	//   - On close: disconnects the client, clears showEmbeds + embed.

	import { tick, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { chatId, embed, showControls, showEmbeds, user, type EmbedDescriptor } from '$lib/stores';
	import Document from '$lib/components/icons/Document.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	import { getOrMintDocIdForChat } from '$lib/integrations/docGen/chatMeta';
	import {
		disconnectDocGenIframe,
		docGenPanelState,
		openDocGenIframe
	} from '$lib/integrations/docGen/store';

	const i18n = getContext<{ t: (k: string) => string }>('i18n');

	// Production override + sensible default for the DG iframe URL. Mirrors
	// the WI-013 iframe-embed.html entry. PUBLIC_RMDG_IFRAME_BASE lets ops
	// point at a non-prod DG without a rebuild.
	const RMDG_IFRAME_BASE =
		(import.meta.env?.VITE_RMDG_IFRAME_BASE as string | undefined) ??
		'https://doc-gen.datameesters.nl';
	const RMDG_IFRAME_ORIGIN = (() => {
		try {
			return new URL(RMDG_IFRAME_BASE).origin;
		} catch {
			return 'https://doc-gen.datameesters.nl';
		}
	})();

	let busy = $state(false);

	// Bugbot HIGH on dc20451: the docgen client + panel are global
	// singletons, but a user can switch chats while the panel is open.
	// If we don't disconnect, completions in the new chat still inject
	// `docgen_*` tools and tool calls still hit the *previous* chat's
	// document. Watch `$chatId` and close the panel on any change.
	// (Initial mount also fires this effect, but `$docGenPanelState.open`
	// is false then so the close is a no-op.)
	let lastChatId: string | null | undefined = undefined;
	$effect(() => {
		const cid = $chatId ?? null;
		if (lastChatId === undefined) {
			lastChatId = cid;
			return;
		}
		if (cid !== lastChatId) {
			lastChatId = cid;
			if ($docGenPanelState.open) closePanel();
		}
	});

	// Bugbot MEDIUM on dc20451 + d121fc9: the embed rail can desync from
	// docgen state in three ways:
	//   1. Embeds.svelte X-button clears `embed` + `showEmbeds` (no docgen
	//      knowledge).
	//   2. Another caller (e.g. Citations) replaces `embed` with a
	//      different descriptor — our iframe is no longer mounted.
	//   3. Another caller flips `showEmbeds` off without nulling `embed`.
	// In all cases the docgen client still tries to postMessage to a now-
	// gone iframe, the model still receives docgen_* tools, and the
	// toolbar still claims the panel is open. Close the panel as soon as
	// the active embed is no longer ours OR the rail is hidden.
	function embedIsOurDocGen(e: EmbedDescriptor | null): boolean {
		return (
			e !== null &&
			e?.trusted === true &&
			typeof e?.url === 'string' &&
			e.url.startsWith(RMDG_IFRAME_BASE)
		);
	}
	$effect(() => {
		if (!$docGenPanelState.open) return;
		const e = $embed as EmbedDescriptor | null;
		if (!embedIsOurDocGen(e) || !$showEmbeds) {
			closePanel();
		}
	});

	async function toggle() {
		if (busy) return;
		busy = true;
		try {
			if ($docGenPanelState.open) {
				closePanel();
				return;
			}
			await openPanel();
		} finally {
			busy = false;
		}
	}

	async function openPanel() {
		const initialChatId = $chatId;
		if (!initialChatId) {
			toast.error(i18n.t('Start een chat voordat je een document opent.'));
			return;
		}
		// Bugbot HIGH on 289a61f7: openPanel awaits getOrMintDocIdForChat
		// and iframe polling. The chat-change effect only fires closePanel
		// when the panel is *already open*; during these awaits the panel
		// isn't open yet, so a chat navigation would leave us mounting
		// the previous chat's docId in the iframe while the visible chat
		// is different. Re-check $chatId after every await and bail if
		// the user has switched away.
		const stillSameChat = () => $chatId === initialChatId;

		let docId: string;
		try {
			docId = await getOrMintDocIdForChat(localStorage.token, initialChatId);
		} catch (err) {
			console.error('docGen: failed to read/mint docId for chat', err);
			toast.error(i18n.t('Kon de document-id voor deze chat niet ophalen.'));
			return;
		}
		if (!stillSameChat()) return;

		const url = `${RMDG_IFRAME_BASE}/iframe-embed.html?docId=${encodeURIComponent(docId)}`;
		// Open the right-rail Embeds panel via the existing store pattern
		// (matches Citations / ContentRenderer usage).
		const descriptor: EmbedDescriptor = { url, title: 'Document', trusted: true };
		embed.set(descriptor as unknown as null);
		await showControls.set(true);
		await showEmbeds.set(true);
		if (!stillSameChat()) {
			showEmbeds.set(false);
			embed.set(null);
			return;
		}
		// Wait for Svelte to mount Embeds.svelte + FullHeightIframe.
		// A single tick() is not enough: FullHeightIframe.setIframeSrc awaits
		// its own tick() before assigning iframeSrc, and the Embeds pane may
		// still be expanding. Poll until the iframe appears or a timeout hits.
		const iframeEl = await waitForEmbedIframe();
		if (!stillSameChat()) {
			showEmbeds.set(false);
			embed.set(null);
			return;
		}
		if (!iframeEl) {
			// Bugbot MEDIUM on dc20451: previous version returned here
			// with `embed` + `showEmbeds` still set, leaving the user
			// with an empty embed rail and no connected client. Clear
			// the stores so the chat returns to its normal layout.
			toast.error(i18n.t('Document-paneel kon niet worden gestart.'));
			console.error('docGen: iframe element not found after panel open');
			showEmbeds.set(false);
			embed.set(null);
			return;
		}
		openDocGenIframe({ iframe: iframeEl, docId, iframeOrigin: RMDG_IFRAME_ORIGIN });
	}

	function closePanel() {
		disconnectDocGenIframe();
		showEmbeds.set(false);
		embed.set(null);
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
		// FullHeightIframe doesn't expose a binding hook to its consumer
		// (it's used by Citations + others as a generic embed shell). The
		// reliable way to grab the iframe element is a DOM query scoped
		// to the embeds panel; there is exactly one iframe in that pane.
		// If FullHeightIframe later exposes a `bind:iframe`, swap to that.
		return document.querySelector<HTMLIFrameElement>(
			'.docgen-embeds-pane iframe, [data-rmdg-embed-host] iframe, iframe[src*="iframe-embed.html"]'
		);
	}
</script>

{#if $user?.role === 'admin' || ($user?.permissions?.chat?.controls ?? true)}
	<Tooltip content={i18n.t($docGenPanelState.open ? 'Document sluiten' : 'Document openen')}>
		<button
			type="button"
			class="flex cursor-pointer px-2 py-2 rounded-xl transition {$docGenPanelState.open
				? 'bg-gray-100 dark:bg-gray-800 text-blue-600 dark:text-blue-400'
				: 'hover:bg-gray-50 dark:hover:bg-gray-850'}"
			onclick={toggle}
			disabled={busy}
			aria-label={i18n.t($docGenPanelState.open ? 'Document sluiten' : 'Document openen')}
			aria-pressed={$docGenPanelState.open}
		>
			<div class="m-auto self-center">
				<Document className="size-5" strokeWidth="1.5" />
			</div>
		</button>
	</Tooltip>
{/if}
