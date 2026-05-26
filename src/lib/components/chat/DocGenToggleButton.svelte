<script lang="ts">
	// Toggle button for the Document-Generator iframe panel (WI-014).
	//
	// Owns the *button* — busy state, chat-change watchdog, embed-rail
	// desync watchdog, click handler. The open-lifecycle itself
	// (mint docId, mount iframe, connect client) was extracted to
	// `panelLifecycle.openDocGenPanelForCurrentChat()` in WI-015 so the
	// `/document` slash command can share it.

	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { chatId, embed, showEmbeds, user, type EmbedDescriptor } from '$lib/stores';
	import Document from '$lib/components/icons/Document.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	import { disconnectDocGenIframe, docGenPanelState } from '$lib/integrations/docGen/store';
	import {
		embedIsDocGenIframe,
		openDocGenPanelForCurrentChat
	} from '$lib/integrations/docGen/panelLifecycle';

	// OWUI's i18n context is a Writable store, not a plain { t }. Auto-
	// subscribe with the $-prefix in both script and template. See
	// Chat.svelte:8 for the canonical declaration pattern.
	const i18n: Writable<i18nType> = getContext('i18n');

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
	$effect(() => {
		if (!$docGenPanelState.open) return;
		const e = $embed as EmbedDescriptor | null;
		if (!embedIsDocGenIframe(e) || !$showEmbeds) {
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
			await openDocGenPanelForCurrentChat({ i18n });
		} finally {
			busy = false;
		}
	}

	function closePanel() {
		disconnectDocGenIframe();
		showEmbeds.set(false);
		embed.set(null);
	}
</script>

{#if $user?.role === 'admin' || ($user?.permissions?.chat?.controls ?? true)}
	<Tooltip content={$i18n.t($docGenPanelState.open ? 'Document sluiten' : 'Document openen')}>
		<button
			type="button"
			class="flex cursor-pointer px-2 py-2 rounded-xl transition {$docGenPanelState.open
				? 'bg-gray-100 dark:bg-gray-800 text-blue-600 dark:text-blue-400'
				: 'hover:bg-gray-50 dark:hover:bg-gray-850'}"
			onclick={toggle}
			disabled={busy}
			aria-label={$i18n.t($docGenPanelState.open ? 'Document sluiten' : 'Document openen')}
			aria-pressed={$docGenPanelState.open}
		>
			<div class="m-auto self-center">
				<Document className="size-10" strokeWidth="1.5" />
			</div>
		</button>
	</Tooltip>
{/if}
