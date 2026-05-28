<script lang="ts">
	import { getContext, onMount } from 'svelte';

	import { user } from '$lib/stores';
	import { getAdoptionStats, type AdoptionStats, type BankStats } from '$lib/apis/admin/memory';

	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n') as any;

	let stats: AdoptionStats | null = null;
	let loading = true;
	let errorMsg: string | null = null;

	const TOP_USERS = 10;

	// Request-token to drop stale responses: if the admin clicks Refresh
	// twice quickly, the first request's response could otherwise arrive
	// after the second and overwrite the fresh stats with old data
	// (Bugbot finding on PR #59).
	let requestId = 0;

	const refresh = async () => {
		const myId = ++requestId;
		loading = true;
		errorMsg = null;
		try {
			const result = await getAdoptionStats(localStorage.token);
			if (myId !== requestId) return; // a newer refresh is in flight; drop
			stats = result;
		} catch (e: any) {
			if (myId !== requestId) return;
			// Always end with a non-empty string so the {:else if errorMsg}
			// branch always renders — an empty string would be falsy and
			// blank the panel (Bugbot finding on PR #59, belt-and-braces).
			const raw = typeof e === 'string' ? e : (e?.detail ?? String(e));
			errorMsg = raw || 'request failed';
			stats = null;
		} finally {
			if (myId === requestId) loading = false;
		}
	};

	onMount(() => {
		if ($user?.role !== 'admin') return;
		refresh();
	});

	const formatTimestamp = (iso: string | null): string => {
		if (!iso) return '—';
		try {
			return new Date(iso).toLocaleString();
		} catch {
			return iso;
		}
	};

	// Aggregate `by_owner` across all banks so the Top users card shows
	// a single ranking instead of per-bank lists. Same prefixed-id
	// convention as the legacy view (`api:<name>` / `clerk:<id>`).
	const aggregateOwners = (banks: BankStats[]): { owner_user_id: string; count: number }[] => {
		const totals = new Map<string, number>();
		for (const b of banks) {
			for (const row of b.by_owner) {
				totals.set(row.owner_user_id, (totals.get(row.owner_user_id) ?? 0) + row.count);
			}
		}
		return [...totals.entries()]
			.map(([owner_user_id, count]) => ({ owner_user_id, count }))
			.sort((a, b) => b.count - a.count || a.owner_user_id.localeCompare(b.owner_user_id));
	};

	$: owners = stats ? aggregateOwners(stats.banks) : [];

	const totalDocs = (banks: BankStats[]): number =>
		banks.reduce((sum, b) => sum + b.document_count, 0);

	const totalFacts = (banks: BankStats[]): number | null => {
		// If ANY bank has a known fact_count, sum them — banks with null
		// (upstream missing) are skipped, and the surfaced number reflects
		// only the banks Hindsight actually knows about.
		let any = false;
		let sum = 0;
		for (const b of banks) {
			if (b.fact_count !== null) {
				any = true;
				sum += b.fact_count;
			}
		}
		return any ? sum : null;
	};
</script>

<svelte:head>
	<title>{$i18n.t('Memory adoption')} · {$i18n.t('Admin')}</title>
</svelte:head>

<div class="px-4 py-3 max-w-5xl mx-auto w-full">
	<div class="flex items-center justify-between mb-4">
		<div>
			<h2 class="text-lg font-semibold">{$i18n.t('Memory adoption')}</h2>
			<p class="text-xs text-gray-500 dark:text-gray-400">
				{$i18n.t('Per-bank counts from')}
				<code>get_adoption_stats</code>. {$i18n.t('Admin only.')}
			</p>
		</div>

		<button
			type="button"
			class="px-2 py-0.5 rounded-sm border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-850 text-sm"
			on:click={refresh}
			disabled={loading}
		>
			{$i18n.t('Refresh')}
		</button>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-10">
			<Spinner className="size-5" />
		</div>
	{:else if errorMsg}
		<div
			class="rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-3 py-2 text-sm text-red-800 dark:text-red-200"
		>
			<div class="font-medium">{$i18n.t("Couldn't load memory stats")}</div>
			<div class="text-xs mt-0.5">{errorMsg}</div>
			{#if errorMsg.toLowerCase().includes('memory_admin_token')}
				<div class="text-xs mt-1 opacity-75">
					{$i18n.t('Set')}
					<code>MEMORY_ADMIN_TOKEN</code>
					{$i18n.t(
						'in the chatbot env (matches the value in MCP-Servers compose) and restart the backend.'
					)}
				</div>
			{/if}
		</div>
	{:else if stats}
		<div class="text-xs text-gray-500 mb-3">
			{$i18n.t('Snapshot at {{measuredAt}}', {
				measuredAt: formatTimestamp(stats.measured_at)
			})}
		</div>

		<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
			<!-- Banks summary card -->
			<section
				class="rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3 md:col-span-2"
			>
				<header class="flex items-baseline justify-between mb-2">
					<h3 class="text-sm font-semibold">{$i18n.t('Banks')}</h3>
					<div class="flex items-baseline gap-3 text-sm">
						<div>
							<span class="text-xs text-gray-500">{$i18n.t('documents')}</span>
							<span class="ml-1 font-semibold">{totalDocs(stats.banks)}</span>
						</div>
						<div>
							<span class="text-xs text-gray-500">{$i18n.t('facts')}</span>
							<span class="ml-1 font-semibold">
								{#if totalFacts(stats.banks) === null}
									—
								{:else}
									{totalFacts(stats.banks)}
								{/if}
							</span>
						</div>
					</div>
				</header>
				{#if stats.banks.length === 0}
					<p class="text-xs text-gray-500">
						{$i18n.t('No banks yet.')}
					</p>
				{:else}
					<table class="w-full text-xs">
						<thead class="text-gray-500">
							<tr>
								<th class="text-left font-normal py-1">{$i18n.t('bank')}</th>
								<th class="text-right font-normal py-1">{$i18n.t('docs')}</th>
								<th class="text-right font-normal py-1">{$i18n.t('facts')}</th>
								<th class="text-left font-normal py-1 pl-3">{$i18n.t('top types')}</th>
								<th class="text-right font-normal py-1">{$i18n.t('last write')}</th>
							</tr>
						</thead>
						<tbody>
							{#each stats.banks as bank}
								<tr class="border-t border-gray-100 dark:border-gray-800">
									<td class="py-1 font-mono">
										{bank.bank_id}
										{#if bank.truncated}
											<span
												class="ml-1 text-xs text-amber-600 dark:text-amber-400"
												title={$i18n.t('Scan ceiling reached — counts are lower bounds')}>⚠</span
											>
										{/if}
									</td>
									<td class="py-1 text-right">{bank.document_count}</td>
									<td class="py-1 text-right">
										{#if bank.fact_count === null}
											<span class="text-gray-400" title={$i18n.t('bank not in /v1/default/banks')}
												>—</span
											>
										{:else}
											{bank.fact_count}
										{/if}
									</td>
									<td class="py-1 pl-3 font-mono text-gray-600 dark:text-gray-400">
										{Object.entries(bank.by_type)
											.sort(([, a], [, b]) => b - a)
											.slice(0, 3)
											.map(([t, n]) => `${t}=${n}`)
											.join(', ') || '—'}
									</td>
									<td class="py-1 text-right text-gray-500">
										{formatTimestamp(bank.last_document_at)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
				<div class="mt-2 text-xs text-gray-500">
					{$i18n.t('{{users}} users · {{projects}} projects', {
						users: stats.users,
						projects: stats.projects
					})}
				</div>
			</section>

			<!-- BOPA sessions card -->
			<section
				class="rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3"
			>
				<header class="flex items-baseline justify-between mb-2">
					<h3 class="text-sm font-semibold">{$i18n.t('BOPA sessions')}</h3>
					<span class="text-2xl font-semibold">{stats.bopa_sessions.total}</span>
				</header>
				<div class="text-sm">
					<span class="font-medium text-emerald-700 dark:text-emerald-400"
						>{stats.bopa_sessions.active}</span
					>
					<span class="text-gray-500"> {$i18n.t('active')}</span>
					<span class="text-gray-400"> · </span>
					<span class="font-medium">{stats.bopa_sessions.total - stats.bopa_sessions.active}</span>
					<span class="text-gray-500"> {$i18n.t('archived/completed')}</span>
				</div>
				{#if stats.bopa_sessions.total === 0}
					<p class="text-xs text-gray-500 mt-2">
						{$i18n.t('No BOPA sessions yet. Try')}
						<code>/bopa-haalbaarheid &lt;adres&gt;</code>
						{$i18n.t('in chat.')}
					</p>
				{/if}
			</section>

			<!-- Top users card (aggregated across banks) -->
			<section
				class="rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3"
			>
				<header class="flex items-baseline justify-between mb-2">
					<h3 class="text-sm font-semibold">
						{$i18n.t('Top users')}
						<span class="text-gray-500 font-normal text-xs"
							>{$i18n.t('(documents across all banks, top {{n}})', { n: TOP_USERS })}</span
						>
					</h3>
				</header>
				{#if owners.length === 0}
					<p class="text-xs text-gray-500">{$i18n.t('No per-user activity yet.')}</p>
				{:else}
					<table class="w-full text-xs">
						<thead class="text-gray-500">
							<tr>
								<th class="text-left font-normal py-1">{$i18n.t('owner_user_id')}</th>
								<th class="text-right font-normal py-1">{$i18n.t('documents')}</th>
							</tr>
						</thead>
						<tbody>
							{#each owners.slice(0, TOP_USERS) as row}
								<tr class="border-t border-gray-100 dark:border-gray-800">
									<td class="py-1 font-mono break-all">{row.owner_user_id}</td>
									<td class="py-1 text-right">{row.count}</td>
								</tr>
							{/each}
						</tbody>
					</table>
					{#if owners.length > TOP_USERS}
						<div class="text-xs text-gray-500 mt-1">
							{$i18n.t('… and {{count}} more', {
								count: owners.length - TOP_USERS
							})}
						</div>
					{/if}
				{/if}
			</section>
		</div>
	{/if}
</div>
