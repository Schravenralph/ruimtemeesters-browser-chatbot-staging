<script lang="ts">
	import { getContext, onMount } from 'svelte';

	import {
		listMemories,
		getMemoryEntry,
		saveMemoryEntry,
		forgetMemoryEntry,
		type MemoryEntry,
		type MemoryDetail,
		type MemoryScope,
		type MemoryType
	} from '$lib/apis/rm-memory';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import MemoryCreateModal from '$lib/components/memory/MemoryCreateModal.svelte';

	const i18n = getContext('i18n') as any;

	// --- state --------------------------------------------------------------

	let entries: MemoryEntry[] = [];
	let callerId: string | null = null;
	let loading = true;
	let errorMsg: string | null = null;
	let showCreate = false;

	let scopeFilter: MemoryScope | 'all' = 'all';
	let typeFilter: MemoryType | 'all' = 'all';
	let projectFilter = '';
	let searchTerm = '';

	let expandedName: string | null = null;
	let expandedDetail: MemoryDetail | null = null;
	let expandedLoading = false;
	let expandedErr: string | null = null;

	let editing = false;
	let editDescription = '';
	let editContent = '';
	let editSaving = false;
	let editErr: string | null = null;

	let forgettingName: string | null = null;
	let forgetErr: string | null = null;

	// Stale-response guard — Bugbot pattern from admin/memory PR #59.
	let listRequestId = 0;
	let detailRequestId = 0;

	// --- helpers ------------------------------------------------------------

	const formatTimestamp = (iso: string): string => {
		try {
			return new Date(iso).toLocaleString();
		} catch {
			return iso;
		}
	};

	const scopeBadgeClass = (scope: string): string => {
		switch (scope) {
			case 'user':
				return 'bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-200';
			case 'project':
				return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200';
			case 'global':
				return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
			default:
				return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
		}
	};

	const canMutate = (entry: MemoryEntry): boolean => {
		// Only the owner can edit/forget. `global`-scope entries are
		// read-only from this panel (admins manage them out-of-band).
		// The BFF surfaces the canonical id it forwarded to rm-memory
		// (`clerk:<sub>` for OAuth users, gateway-key name for direct-login
		// admins) — compare against that, not against `$user.id` (which is
		// the OWUI UUID and never matches the MCP's prefixed identities).
		if (!callerId) return false;
		return entry.scope !== 'global' && entry.owner_user_id === callerId;
	};

	$: filteredEntries = (() => {
		const q = searchTerm.trim().toLowerCase();
		const filtered = entries.filter((e) => {
			if (scopeFilter !== 'all' && e.scope !== scopeFilter) return false;
			if (typeFilter !== 'all' && e.type !== typeFilter) return false;
			if (projectFilter.trim() && e.project_id !== projectFilter.trim()) return false;
			if (q) {
				const hay = `${e.name} ${e.description}`.toLowerCase();
				if (!hay.includes(q)) return false;
			}
			return true;
		});
		// Dedupe by (name, scope, project_id) — the same composite key used by
		// {#each} below. Some backends can return multiple rows for the same
		// composite (e.g. mid-migration state in rm-memory); we keep the most
		// recently updated copy so the row count matches what forget can act on.
		const seen = new Map<string, MemoryEntry>();
		for (const e of filtered) {
			const k = `${e.name}:${e.scope}:${e.project_id ?? ''}`;
			const prev = seen.get(k);
			if (!prev || prev.updated_at < e.updated_at) seen.set(k, e);
		}
		return Array.from(seen.values());
	})();

	$: knownProjects = Array.from(
		new Set(entries.map((e) => e.project_id).filter((p): p is string => !!p))
	).sort();

	// --- data fetch ---------------------------------------------------------

	const refresh = async () => {
		const myId = ++listRequestId;
		loading = true;
		errorMsg = null;
		try {
			const result = await listMemories(localStorage.token, { limit: 200 });
			if (myId !== listRequestId) return;
			entries = result.entries;
			callerId = result.caller_id ?? null;
		} catch (e: any) {
			if (myId !== listRequestId) return;
			const raw = typeof e === 'string' ? e : (e?.detail ?? String(e));
			errorMsg = raw || 'request failed';
			entries = [];
			callerId = null;
		} finally {
			if (myId === listRequestId) loading = false;
		}
	};

	const expand = async (entry: MemoryEntry) => {
		if (expandedName === entry.name && expandedDetail) {
			// already open — toggle close
			expandedName = null;
			expandedDetail = null;
			editing = false;
			return;
		}
		const myId = ++detailRequestId;
		expandedName = entry.name;
		expandedDetail = null;
		expandedLoading = true;
		expandedErr = null;
		editing = false;
		try {
			const detail = await getMemoryEntry(localStorage.token, entry.name, {
				type: entry.type as MemoryType,
				project_id: entry.project_id ?? undefined
			});
			if (myId !== detailRequestId) return;
			expandedDetail = detail;
		} catch (e: any) {
			if (myId !== detailRequestId) return;
			const raw = typeof e === 'string' ? e : (e?.detail ?? String(e));
			expandedErr = raw || 'request failed';
		} finally {
			if (myId === detailRequestId) expandedLoading = false;
		}
	};

	const startEdit = () => {
		if (!expandedDetail) return;
		editing = true;
		editDescription = expandedDetail.description;
		editContent = expandedDetail.content;
		editErr = null;
	};

	const cancelEdit = () => {
		editing = false;
		editErr = null;
	};

	const saveEdit = async () => {
		if (!expandedDetail) return;
		editSaving = true;
		editErr = null;
		try {
			await saveMemoryEntry(localStorage.token, {
				name: expandedDetail.name,
				description: editDescription,
				type: expandedDetail.type as MemoryType,
				content: editContent,
				scope: expandedDetail.scope as MemoryScope,
				project_id: expandedDetail.project_id ?? undefined
			});
			// Re-fetch detail + list to reflect the upsert
			editing = false;
			await refresh();
			if (expandedDetail) {
				const refreshed = await getMemoryEntry(localStorage.token, expandedDetail.name, {
					type: expandedDetail.type as MemoryType,
					project_id: expandedDetail.project_id ?? undefined
				});
				expandedDetail = refreshed;
			}
		} catch (e: any) {
			const raw = typeof e === 'string' ? e : (e?.detail ?? String(e));
			editErr = raw || 'save failed';
		} finally {
			editSaving = false;
		}
	};

	const forget = async (entry: MemoryEntry) => {
		if (!canMutate(entry)) return;
		const confirmed = window.confirm(
			$i18n.t('Permanently forget memory "{{name}}"? This cannot be undone.', { name: entry.name })
		);
		if (!confirmed) return;
		forgettingName = entry.name;
		forgetErr = null;
		try {
			await forgetMemoryEntry(localStorage.token, entry.name, {
				type: entry.type as MemoryType,
				scope: entry.scope as MemoryScope,
				project_id: entry.project_id ?? undefined
			});
			if (expandedName === entry.name) {
				expandedName = null;
				expandedDetail = null;
				editing = false;
			}
			await refresh();
		} catch (e: any) {
			const raw = typeof e === 'string' ? e : (e?.detail ?? String(e));
			forgetErr = raw || 'forget failed';
		} finally {
			forgettingName = null;
		}
	};

	onMount(refresh);
</script>

<svelte:head>
	<title>{$i18n.t('Memory')} · {$i18n.t('Ruimtemeesters')}</title>
</svelte:head>

<div class="px-4 py-3 max-w-5xl mx-auto w-full">
	<div class="flex flex-col gap-1 mb-4">
		<h2 class="text-lg font-semibold">{$i18n.t('Memory')}</h2>
		<p class="text-xs text-gray-500 dark:text-gray-400">
			{$i18n.t(
				'Everything the assistant has remembered for you, across personal, project, and shared scopes. Edit or forget entries you own; global entries are read-only.'
			)}
		</p>
	</div>

	<!-- Filters -->
	<div class="flex flex-wrap items-end gap-2 mb-3 text-sm">
		<div class="flex flex-col">
			<label for="scope" class="text-xs text-gray-500">{$i18n.t('Scope')}</label>
			<select
				id="scope"
				bind:value={scopeFilter}
				class="rounded-sm bg-transparent border border-gray-200 dark:border-gray-700 px-2 py-1"
			>
				<option value="all">{$i18n.t('All scopes')}</option>
				<option value="user">{$i18n.t('User')}</option>
				<option value="project">{$i18n.t('Project')}</option>
				<option value="global">{$i18n.t('Global')}</option>
			</select>
		</div>
		<div class="flex flex-col">
			<label for="type" class="text-xs text-gray-500">{$i18n.t('Type')}</label>
			<select
				id="type"
				bind:value={typeFilter}
				class="rounded-sm bg-transparent border border-gray-200 dark:border-gray-700 px-2 py-1"
			>
				<option value="all">{$i18n.t('All types')}</option>
				<option value="user">user</option>
				<option value="feedback">feedback</option>
				<option value="project">project</option>
				<option value="reference">reference</option>
				<option value="session-summary">session-summary</option>
			</select>
		</div>
		<div class="flex flex-col flex-1 min-w-[12rem]">
			<label for="project" class="text-xs text-gray-500">{$i18n.t('Project id')}</label>
			<input
				id="project"
				list="known-projects"
				bind:value={projectFilter}
				placeholder={$i18n.t('e.g. beleidsscan:GM0344:energietransitie')}
				class="rounded-sm bg-transparent border border-gray-200 dark:border-gray-700 px-2 py-1"
			/>
			<datalist id="known-projects">
				{#each knownProjects as p}
					<option value={p}></option>
				{/each}
			</datalist>
		</div>
		<div class="flex flex-col flex-1 min-w-[12rem]">
			<label for="search" class="text-xs text-gray-500">{$i18n.t('Search')}</label>
			<input
				id="search"
				type="search"
				bind:value={searchTerm}
				placeholder={$i18n.t('name or description')}
				class="rounded-sm bg-transparent border border-gray-200 dark:border-gray-700 px-2 py-1"
			/>
		</div>
		<button
			type="button"
			class="px-2 py-1 rounded-sm border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-850"
			on:click={refresh}
			disabled={loading}
		>
			{$i18n.t('Refresh')}
		</button>
		<button
			type="button"
			class="px-2 py-1 rounded-sm border border-gray-900 dark:border-gray-100
			       bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900
			       hover:bg-gray-800 dark:hover:bg-gray-200 transition"
			on:click={() => (showCreate = true)}
		>
			+ {$i18n.t('New memory')}
		</button>
	</div>

	<MemoryCreateModal
		bind:show={showCreate}
		on:created={() => {
			void refresh();
		}}
	/>

	<!-- Status / errors -->
	{#if loading}
		<div class="flex items-center justify-center py-10">
			<Spinner className="size-5" />
		</div>
	{:else if errorMsg}
		<div
			class="rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-3 py-2 text-sm text-red-800 dark:text-red-200"
		>
			<div class="font-medium">{$i18n.t("Couldn't load memories")}</div>
			<div class="text-xs mt-0.5">{errorMsg}</div>
			{#if errorMsg.toLowerCase().includes('memory_gateway_token')}
				<div class="text-xs mt-1 opacity-75">
					{$i18n.t('Set')}
					<code>MEMORY_GATEWAY_TOKEN</code>
					{$i18n.t('in the chatbot env and restart the backend.')}
				</div>
			{/if}
		</div>
	{:else if filteredEntries.length === 0}
		<div class="text-sm text-gray-500 py-8 text-center">
			{#if entries.length === 0}
				{$i18n.t('No memories yet. The assistant will save them as you chat.')}
			{:else}
				{$i18n.t('No memories match the current filters.')}
			{/if}
		</div>
	{:else}
		<div class="text-xs text-gray-500 mb-2">
			{$i18n.t('{{visible}} of {{total}} entries', {
				visible: filteredEntries.length,
				total: entries.length
			})}
		</div>

		{#if forgetErr}
			<div
				class="rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-3 py-2 mb-2 text-sm text-red-800 dark:text-red-200"
			>
				{forgetErr}
			</div>
		{/if}

		<ul class="flex flex-col gap-2">
			{#each filteredEntries as entry (entry.name + ':' + entry.scope + ':' + (entry.project_id ?? ''))}
				<li
					class="rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900"
				>
					<button
						type="button"
						class="w-full text-left px-3 py-2 flex flex-col gap-1 hover:bg-gray-50 dark:hover:bg-gray-850 rounded-md"
						on:click={() => expand(entry)}
					>
						<div class="flex flex-wrap items-center gap-2">
							<span class="font-mono text-sm">{entry.name}</span>
							<span class="text-[10px] px-1.5 py-0.5 rounded {scopeBadgeClass(entry.scope)}">
								{entry.scope}
							</span>
							<span
								class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
							>
								{entry.type}
							</span>
							{#if entry.project_id}
								<span class="text-[10px] font-mono text-gray-500">
									{entry.project_id}
								</span>
							{/if}
							<span class="text-[10px] text-gray-400 ml-auto">
								{formatTimestamp(entry.updated_at)}
							</span>
						</div>
						<div class="text-xs text-gray-700 dark:text-gray-300">{entry.description}</div>
					</button>

					{#if expandedName === entry.name}
						<div class="border-t border-gray-200 dark:border-gray-800 px-3 py-2">
							{#if expandedLoading}
								<div class="flex items-center gap-2 text-xs text-gray-500">
									<Spinner className="size-4" />
									{$i18n.t('Loading…')}
								</div>
							{:else if expandedErr}
								<div class="text-xs text-red-700 dark:text-red-400">{expandedErr}</div>
							{:else if expandedDetail}
								{#if editing}
									<div class="flex flex-col gap-2">
										<label for="edit-description" class="text-xs text-gray-500"
											>{$i18n.t('Description')}</label
										>
										<input
											id="edit-description"
											type="text"
											bind:value={editDescription}
											maxlength="200"
											class="rounded-sm bg-transparent border border-gray-200 dark:border-gray-700 px-2 py-1 text-sm"
										/>
										<label for="edit-content" class="text-xs text-gray-500"
											>{$i18n.t('Content')}</label
										>
										<textarea
											id="edit-content"
											bind:value={editContent}
											maxlength="65536"
											rows="6"
											class="rounded-sm bg-transparent border border-gray-200 dark:border-gray-700 px-2 py-1 text-sm font-mono"
										></textarea>
										{#if editErr}
											<div class="text-xs text-red-700 dark:text-red-400">{editErr}</div>
										{/if}
										<div class="flex items-center gap-2">
											<button
												type="button"
												class="px-2 py-1 text-xs rounded-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
												on:click={saveEdit}
												disabled={editSaving || !editDescription.trim() || !editContent.trim()}
											>
												{editSaving ? $i18n.t('Saving…') : $i18n.t('Save')}
											</button>
											<button
												type="button"
												class="px-2 py-1 text-xs rounded-sm border border-gray-200 dark:border-gray-700"
												on:click={cancelEdit}
												disabled={editSaving}
											>
												{$i18n.t('Cancel')}
											</button>
										</div>
									</div>
								{:else}
									<pre
										class="text-xs font-mono whitespace-pre-wrap break-words text-gray-800 dark:text-gray-200">{expandedDetail.content}</pre>
									<div class="flex items-center gap-2 mt-2 text-[10px] text-gray-500">
										<span>{$i18n.t('Created')}: {formatTimestamp(expandedDetail.created_at)}</span>
										<span>·</span>
										<span>{$i18n.t('Updated')}: {formatTimestamp(expandedDetail.updated_at)}</span>
									</div>
									<div class="flex items-center gap-2 mt-2">
										{#if canMutate(entry)}
											<button
												type="button"
												class="px-2 py-1 text-xs rounded-sm border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-850"
												on:click={startEdit}
											>
												{$i18n.t('Edit')}
											</button>
											<button
												type="button"
												class="px-2 py-1 text-xs rounded-sm border border-red-200 dark:border-red-900 text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 disabled:opacity-50"
												on:click={() => forget(entry)}
												disabled={forgettingName === entry.name}
											>
												{forgettingName === entry.name ? $i18n.t('Forgetting…') : $i18n.t('Forget')}
											</button>
										{:else}
											<span class="text-[10px] text-gray-500"
												>{$i18n.t('Read-only — shared scope')}</span
											>
										{/if}
									</div>
								{/if}
							{/if}
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>
