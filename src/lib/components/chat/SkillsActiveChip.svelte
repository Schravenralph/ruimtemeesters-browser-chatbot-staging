<script lang="ts">
	import { getActiveSkills, type ActiveSkill } from '$lib/apis/rm-skills';

	export let selectedModels: string[] = [];

	// Same persona map as the skills_context inlet filter
	// (rm-tools/filters/skills_context.py:_PERSONA_MAP) — kept in sync so
	// the chip can't disagree with what the LLM actually receives. Mirror
	// of the seed names in scripts/personas.yaml.
	const PERSONA_MAP: Record<string, string> = {
		'rm-assistent': 'ro-assistent',
		'rm-ro-assistent': 'ro-assistent',
		'rm-juridisch-assistent': 'juridisch-assistent',
		'rm-commercieel-assistent': 'commercieel-assistent',
		'ro-assistent': 'ro-assistent',
		'juridisch-assistent': 'juridisch-assistent',
		'commercieel-assistent': 'commercieel-assistent',
		'RO-Assistent': 'ro-assistent',
		'Juridisch-Assistent': 'juridisch-assistent',
		'Commercieel-Assistent': 'commercieel-assistent'
	};

	const resolvePersona = (modelId: string | undefined | null): string => {
		if (!modelId) return '';
		const trimmed = modelId.trim();
		if (PERSONA_MAP[trimmed]) return PERSONA_MAP[trimmed];
		const lc = trimmed.toLowerCase();
		if (PERSONA_MAP[lc]) return PERSONA_MAP[lc];
		// Last-chance fallback: strip rm- prefix.
		return lc.startsWith('rm-') ? lc.slice(3) : lc;
	};

	let skills: ActiveSkill[] = [];
	let persona = '';
	let open = false;
	let fetchGen = 0;

	const refresh = async (modelId: string | undefined) => {
		const myGen = ++fetchGen;
		const slug = resolvePersona(modelId);
		if (!slug) {
			if (myGen === fetchGen) {
				persona = '';
				skills = [];
			}
			return;
		}
		const result = await getActiveSkills(localStorage.token, slug);
		if (myGen !== fetchGen) return;
		if (!result) {
			// `getActiveSkills` returns null only on transport failure (it
			// already soft-fails). Hide the chip rather than render
			// "Skills: 0", which would mislead the user — the
			// `skills_context` filter may still be injecting skills via a
			// direct rm-skills path that doesn't touch the BFF.
			persona = '';
			skills = [];
			return;
		}
		persona = result.persona || slug;
		skills = result.skills ?? [];
	};

	// Refetch on persona change. The filter inside Chat.svelte resolves
	// persona per request from `selectedModels[0]`; mirror that here so
	// the chip can't disagree with what the LLM receives.
	let lastSeenModel: string | null = null;
	$: if (typeof window !== 'undefined') {
		const current = selectedModels?.[0] ?? null;
		if (current !== lastSeenModel) {
			lastSeenModel = current;
			void refresh(current ?? undefined);
		}
	}

	// Close popover on outside click. Tracked at the document level
	// because Svelte's `use:clickOutside` action isn't available here.
	let rootEl: HTMLDivElement | undefined;
	const handleDocumentClick = (e: MouseEvent) => {
		if (!open || !rootEl) return;
		if (!rootEl.contains(e.target as Node)) open = false;
	};
</script>

<svelte:document on:click={handleDocumentClick} />

{#if persona}
	<div class="relative inline-flex" bind:this={rootEl}>
		<button
			type="button"
			class="skills-active-chip inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium
			       bg-gray-50 dark:bg-gray-850 text-gray-700 dark:text-gray-300
			       ring-1 ring-inset ring-gray-200 dark:ring-gray-700
			       hover:bg-gray-100 dark:hover:bg-gray-800 transition"
			aria-haspopup="true"
			aria-expanded={open}
			aria-label="Skills active: {skills.length}"
			title="Mandatory skills loaded into the system prompt for this persona"
			on:click|stopPropagation={() => (open = !open)}
		>
			<span aria-hidden="true">🧠</span>
			<span>Skills: {skills.length}</span>
		</button>

		{#if open}
			<div
				role="dialog"
				aria-label="Active skills"
				class="absolute right-0 top-full mt-1 z-40 w-80 max-w-[90vw]
				       rounded-md bg-white dark:bg-gray-900 shadow-lg
				       ring-1 ring-gray-200 dark:ring-gray-700
				       p-3 text-sm"
			>
				<div class="font-medium text-gray-900 dark:text-gray-100 mb-1.5">
					Skills loaded for {persona}
				</div>
				{#if skills.length === 0}
					<p class="text-gray-500 dark:text-gray-400">
						No persona-mandatory skills are loaded into this chat.
					</p>
				{:else}
					<ul class="space-y-2">
						{#each skills as s (s.name)}
							<li>
								<div class="font-mono text-xs text-gray-900 dark:text-gray-100">
									{s.name}
								</div>
								<div class="text-xs text-gray-600 dark:text-gray-400 leading-snug">
									{s.description}
								</div>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		{/if}
	</div>
{/if}
