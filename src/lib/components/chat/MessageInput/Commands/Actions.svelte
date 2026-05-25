<script lang="ts">
	// Slash-action dropdown section (WI-015).
	//
	// Renders the slashActions registry, filtered by the query the user
	// has typed after `/`. Selection emits `onSelect({ type: 'action',
	// data: action })` — the parent (Slash.svelte / CommandSuggestionList)
	// routes that to a different handler than the Prompts `type: 'prompt'`
	// path: actions get their `run()` called; prompts get their text
	// inserted.

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import {
		filterSlashActions,
		type SlashAction
	} from '$lib/integrations/slashActions/registry';

	export let query = '';
	export let onSelect: (e: { type: 'action'; data: SlashAction }) => void = () => {};

	let selectedIdx = 0;
	export let filteredItems: SlashAction[] = [];

	$: filteredItems = filterSlashActions(query);

	$: if (query !== undefined) {
		// Keep the cursor in range whenever the filter changes.
		if (selectedIdx > filteredItems.length - 1) {
			selectedIdx = Math.max(0, filteredItems.length - 1);
		}
	}

	export const selectUp = () => {
		selectedIdx = Math.max(0, selectedIdx - 1);
	};
	export const selectDown = () => {
		selectedIdx = Math.min(selectedIdx + 1, filteredItems.length - 1);
	};
	export const select = () => {
		const action = filteredItems[selectedIdx];
		if (action) onSelect({ type: 'action', data: action });
	};

	// Composite controller (Slash.svelte) needs to drive `selectedIdx`
	// directly when its global cursor lands inside the Actions section.
	export const setSelectedIdx = (idx: number) => {
		if (idx < 0 || idx >= filteredItems.length) return;
		selectedIdx = idx;
	};
	export const clearSelected = () => {
		selectedIdx = -1;
	};
</script>

{#if filteredItems.length > 0}
	<div class="px-2 text-xs text-gray-500 py-1">Acties</div>
	<div class="space-y-0.5 scrollbar-hidden">
		{#each filteredItems as action, actionIdx}
			<Tooltip content={action.description} placement="top-start">
				<button
					class="px-3 py-1 rounded-xl w-full text-left {actionIdx === selectedIdx
						? 'bg-gray-50 dark:bg-gray-800 selected-command-option-button'
						: ''} truncate"
					type="button"
					on:click={() => onSelect({ type: 'action', data: action })}
					on:mousemove={() => {
						selectedIdx = actionIdx;
					}}
					on:focus={() => {}}
					data-selected={actionIdx === selectedIdx}
				>
					<span class="font-medium text-black dark:text-gray-100">
						{#if action.icon}{action.icon}{/if} /{action.id}
					</span>
					<span class="text-xs text-gray-600 dark:text-gray-300 ml-1">
						{action.label}
					</span>
				</button>
			</Tooltip>
		{/each}
	</div>
{/if}
