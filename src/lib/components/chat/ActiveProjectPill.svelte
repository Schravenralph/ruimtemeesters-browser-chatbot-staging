<script lang="ts">
	import { chatId } from '$lib/stores';
	import { getActiveProject, type ActiveProject } from '$lib/apis/rm-memory';
	import { onMount } from 'svelte';

	let active: ActiveProject | null = null;
	let copied = false;

	const refresh = async (id: string | null | undefined) => {
		if (!id || (id ?? '').startsWith('local:')) {
			// Temporary chats have no thread id the memory service can scope.
			active = null;
			return;
		}
		active = await getActiveProject(localStorage.token, id);
	};

	// Refetch whenever the chat we're looking at changes. The first load
	// runs after mount so we don't hit the BFF before localStorage is
	// available (SSR safety).
	let lastSeenId: string | null = null;
	$: if (typeof window !== 'undefined' && $chatId !== lastSeenId) {
		lastSeenId = $chatId ?? null;
		void refresh($chatId);
	}

	onMount(() => void refresh($chatId));

	// "beleidsscan:GM0344:energietransitie" → "Utrecht / energietransitie"
	// when there is no human-friendly label, fall back to the slug parts.
	const renderTitle = (p: ActiveProject): string => {
		if (p.label && p.label.trim()) return p.label;
		const parts = p.project_id.split(':');
		if (parts.length >= 3) {
			// kind:scope:slug → "scope / slug"
			return `${parts[1]} / ${parts.slice(2).join(':')}`;
		}
		return p.project_id;
	};

	const kindIcon = (kind: string): string => {
		switch (kind) {
			case 'beleidsscan':
				return '📂';
			case 'bopa':
				return '⚖️';
			case 'onderbouwing':
				return '📄';
			default:
				return '🔖';
		}
	};

	const copyId = async () => {
		if (!active) return;
		try {
			await navigator.clipboard.writeText(active.project_id);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			// clipboard API can fail in non-secure contexts; silent.
		}
	};
</script>

{#if active}
	<button
		type="button"
		class="active-project-pill inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium
		       bg-gray-50 dark:bg-gray-850 text-gray-700 dark:text-gray-300
		       ring-1 ring-inset ring-gray-200 dark:ring-gray-700
		       hover:bg-gray-100 dark:hover:bg-gray-800 transition
		       max-w-[280px] truncate"
		title={copied
			? `Copied: ${active.project_id}`
			: `${active.project_id}\n(klik om project_id te kopiëren)`}
		aria-label="Active project: {renderTitle(active)}"
		on:click={copyId}
	>
		<span aria-hidden="true">{kindIcon(active.kind)}</span>
		<span class="truncate">{renderTitle(active)}</span>
	</button>
{/if}
