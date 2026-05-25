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
	$: syncChildSelection(globalIdx);

	function syncChildSelection(idx: number) {
		// Highlight the cursor's location in the right child, clear the
		// other. setSelectedIdx is a no-op outside the child's range.
		if (idx < actionItems.length) {
			actionsEl?.setSelectedIdx?.(idx);
			promptsEl?.clearSelected?.();
		} else {
			actionsEl?.clearSelected?.();
			promptsEl?.setSelectedIdx?.(idx - actionItems.length);
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
