<script lang="ts">
	// Composite renderer for the `/` autocomplete dropdown (WI-015).
	//
	// Renders Actions on top of Prompts in a single dropdown, with one
	// shared keyboard cursor that cycles through:
	//   [...actionItems, ...promptItems]
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

	$: filteredItems = [...actionItems, ...promptItems];

	let globalIdx = 0;
	$: if (query !== undefined) {
		// Reset cursor on every query change; matches the behaviour the
		// stock Prompts component had before.
		globalIdx = 0;
	}

	// Re-run on *any* dependency change — globalIdx, actionItems, or
	// promptItems. Bugbot PR #132 follow-up: with only `globalIdx` as
	// the dependency, `$user` loading mid-mount could shift `actionItems`
	// from `[]` to `[document]` (or vice versa) without re-syncing the
	// child highlights, leaving `selectedPromptIdx` at a stale index and
	// causing Enter to fire the wrong row.
	$: syncCursor(globalIdx, actionItems.length, promptItems.length);

	function syncCursor(idx: number, actionLen: number, promptLen: number) {
		const total = actionLen + promptLen;
		if (total === 0) {
			actionsEl?.clearSelected?.();
			promptsEl?.clearSelected?.();
			return;
		}
		// Clamp into the current combined range. Writing back to globalIdx
		// triggers a re-run of this reactive block with the clamped value,
		// which is then in-range and proceeds to the sync below.
		if (idx > total - 1) {
			globalIdx = total - 1;
			return;
		}
		if (idx < 0) {
			globalIdx = 0;
			return;
		}
		if (idx < actionLen) {
			actionsEl?.setSelectedIdx?.(idx);
			promptsEl?.clearSelected?.();
		} else {
			actionsEl?.clearSelected?.();
			promptsEl?.setSelectedIdx?.(idx - actionLen);
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
		// Re-check the section boundary at call time. The child's
		// `selectedIdx` is whatever the latest `syncCursor` set it to,
		// so delegating to the right child fires the highlighted row.
		if (globalIdx < actionItems.length) {
			actionsEl?.select?.();
		} else {
			promptsEl?.select?.();
		}
	};
</script>

<Actions
	bind:this={actionsEl}
	{query}
	bind:filteredItems={actionItems}
	onSelect={(e) => onSelect(e)}
	onHover={(localIdx) => (globalIdx = localIdx)}
/>
<Prompts
	bind:this={promptsEl}
	{query}
	bind:filteredItems={promptItems}
	onSelect={(e) => onSelect(e)}
	onHover={(localIdx) => (globalIdx = actionItems.length + localIdx)}
/>
