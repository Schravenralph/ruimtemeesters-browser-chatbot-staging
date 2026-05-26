<script lang="ts">
	// Composite renderer for the `/` autocomplete dropdown (WI-015).
	//
	// Renders Prompts on top, Actions below, in a single dropdown with
	// one shared keyboard cursor that cycles through:
	//   [...promptItems, ...actionItems]
	//
	// Each child component still tracks its own per-section selectedIdx
	// (so click highlighting works locally and selection inside the
	// section is self-contained). This composite owns a single
	// `globalIdx` and dispatches selectUp/selectDown/select to the
	// right child by computing which section the cursor is in.

	import Actions from './Actions.svelte';
	import Prompts from './Prompts.svelte';

	export let query = '';
	export let onSelect = (e: { type: 'action' | 'prompt'; data: any }) => {};
	export let filteredItems: any[] = [];

	let actionsEl: any = null;
	let promptsEl: any = null;

	let actionItems: any[] = [];
	let promptItems: any[] = [];

	$: filteredItems = [...promptItems, ...actionItems];

	let globalIdx = 0;
	$: if (query !== undefined) {
		// Reset cursor on every query change; matches the behaviour the
		// stock Prompts component had before.
		globalIdx = 0;
	}

	// Re-run on *any* dependency change — globalIdx, promptItems, or
	// actionItems. Bugbot PR #132 follow-up: with only `globalIdx` as
	// the dependency, `$user` loading mid-mount could shift `actionItems`
	// from `[]` to `[document]` (or vice versa) without re-syncing the
	// child highlights, leaving `selectedPromptIdx` at a stale index and
	// causing Enter to fire the wrong row.
	$: syncCursor(globalIdx, promptItems.length, actionItems.length);

	function syncCursor(idx: number, promptLen: number, actionLen: number) {
		const total = promptLen + actionLen;
		if (total === 0) {
			promptsEl?.clearSelected?.();
			actionsEl?.clearSelected?.();
			return;
		}
		if (idx > total - 1) {
			globalIdx = total - 1;
			return;
		}
		if (idx < 0) {
			globalIdx = 0;
			return;
		}
		if (idx < promptLen) {
			promptsEl?.setSelectedIdx?.(idx);
			actionsEl?.clearSelected?.();
		} else {
			promptsEl?.clearSelected?.();
			actionsEl?.setSelectedIdx?.(idx - promptLen);
		}
	}

	export const selectUp = () => {
		globalIdx = Math.max(0, globalIdx - 1);
	};
	export const selectDown = () => {
		globalIdx = Math.min(globalIdx + 1, filteredItems.length - 1);
	};
	export const select = () => {
		if (filteredItems.length === 0) return;
		if (globalIdx < promptItems.length) {
			promptsEl?.select?.();
		} else {
			actionsEl?.select?.();
		}
	};
</script>

<Prompts
	bind:this={promptsEl}
	{query}
	bind:filteredItems={promptItems}
	onSelect={(e) => onSelect(e)}
	onHover={(localIdx) => (globalIdx = localIdx)}
/>
<Actions
	bind:this={actionsEl}
	{query}
	bind:filteredItems={actionItems}
	onSelect={(e) => onSelect(e)}
	onHover={(localIdx) => (globalIdx = promptItems.length + localIdx)}
/>
