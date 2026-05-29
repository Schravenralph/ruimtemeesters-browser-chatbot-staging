<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Modal from '$lib/components/common/Modal.svelte';
	import {
		saveMemoryEntry,
		type MemoryScope,
		type MemoryType
	} from '$lib/apis/rm-memory';

	const i18n = getContext('i18n') as any;
	const dispatch = createEventDispatcher<{ created: { name: string } }>();

	export let show = false;

	// Field bounds mirror the Pydantic invariant in
	// backend/open_webui/routers/rm_memory.py:SaveMemoryRequest — kept in
	// sync so the client catches the same gaps the BFF would 422 on.
	const NAME_MAX = 120;
	const DESCRIPTION_MAX = 200;
	const CONTENT_MAX = 65536;

	const TYPE_OPTIONS: MemoryType[] = ['user', 'feedback', 'project', 'reference'];
	const SCOPE_OPTIONS: MemoryScope[] = ['user', 'project', 'global'];

	let name = '';
	let description = '';
	let content = '';
	let type: MemoryType = 'user';
	let scope: MemoryScope = 'user';
	let projectId = '';

	let saving = false;
	let err: string | null = null;

	const reset = () => {
		name = '';
		description = '';
		content = '';
		type = 'user';
		scope = 'user';
		projectId = '';
		err = null;
		saving = false;
	};

	$: if (!show) {
		// Reset whenever the modal closes so the next open starts blank.
		// Bound `show` makes the parent the source of truth — we just
		// clean up after the fade.
		setTimeout(reset, 200);
	}

	const validate = (): string | null => {
		if (!name.trim()) return $i18n.t('Name is required.');
		if (name.length > NAME_MAX) return $i18n.t('Name must be ≤120 chars.');
		if (!description.trim()) return $i18n.t('Description is required.');
		if (description.length > DESCRIPTION_MAX) return $i18n.t('Description must be ≤200 chars.');
		if (!content.trim()) return $i18n.t('Content is required.');
		if (content.length > CONTENT_MAX) return $i18n.t('Content must be ≤65 536 chars.');
		// Scope ↔ project_id invariant — must match the Pydantic
		// model_validator in SaveMemoryRequest.
		if (scope === 'project' && !projectId.trim()) {
			return $i18n.t("project_id is required when scope='project'.");
		}
		if (scope !== 'project' && projectId.trim()) {
			return $i18n.t("project_id must be empty unless scope='project'.");
		}
		return null;
	};

	const submit = async () => {
		err = validate();
		if (err) return;
		saving = true;
		try {
			const result = await saveMemoryEntry(localStorage.token, {
				name: name.trim(),
				description: description.trim(),
				type,
				content,
				scope,
				project_id: scope === 'project' ? projectId.trim() : undefined
			});
			toast.success(
				result?.updated
					? $i18n.t('Memory updated.')
					: $i18n.t('Memory created.')
			);
			dispatch('created', { name: name.trim() });
			show = false;
		} catch (e: any) {
			err = typeof e === 'string' ? e : (e?.detail ?? e?.message ?? $i18n.t('Save failed.'));
		} finally {
			saving = false;
		}
	};
</script>

<Modal bind:show size="sm">
	<div class="px-5 pt-5 pb-2">
		<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
			{$i18n.t('New memory')}
		</h2>
		<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
			{$i18n.t('Stored in the chatbot memory layer; visible across future chats.')}
		</p>
	</div>

	<form
		on:submit|preventDefault={submit}
		class="px-5 pb-5 pt-2 space-y-3 text-sm"
		autocomplete="off"
	>
		<div>
			<label for="memory-create-name" class="block text-xs font-medium mb-1 text-gray-700 dark:text-gray-300">
				{$i18n.t('Name')} <span class="text-red-500">*</span>
			</label>
			<input
				id="memory-create-name"
				type="text"
				bind:value={name}
				maxlength={NAME_MAX}
				placeholder="ralph-bopa-stijl"
				class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900
				       px-2 py-1.5 font-mono text-xs"
				required
			/>
			<p class="text-[10px] text-gray-500 mt-0.5">
				{$i18n.t('Short identifier — re-saving with the same (scope, type, name) overwrites.')}
			</p>
		</div>

		<div>
			<label for="memory-create-description" class="block text-xs font-medium mb-1 text-gray-700 dark:text-gray-300">
				{$i18n.t('Description')} <span class="text-red-500">*</span>
			</label>
			<input
				id="memory-create-description"
				type="text"
				bind:value={description}
				maxlength={DESCRIPTION_MAX}
				placeholder={$i18n.t('One-sentence summary, shown in the panel list.')}
				class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900
				       px-2 py-1.5"
				required
			/>
		</div>

		<div class="grid grid-cols-2 gap-3">
			<div>
				<label for="memory-create-type" class="block text-xs font-medium mb-1 text-gray-700 dark:text-gray-300">
					{$i18n.t('Type')}
				</label>
				<select
					id="memory-create-type"
					bind:value={type}
					class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900
					       px-2 py-1.5"
				>
					{#each TYPE_OPTIONS as opt}
						<option value={opt}>{opt}</option>
					{/each}
				</select>
			</div>

			<div>
				<label for="memory-create-scope" class="block text-xs font-medium mb-1 text-gray-700 dark:text-gray-300">
					{$i18n.t('Scope')}
				</label>
				<select
					id="memory-create-scope"
					bind:value={scope}
					class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900
					       px-2 py-1.5"
				>
					{#each SCOPE_OPTIONS as opt}
						<option value={opt}>{opt}</option>
					{/each}
				</select>
			</div>
		</div>

		{#if scope === 'project'}
			<div>
				<label for="memory-create-project" class="block text-xs font-medium mb-1 text-gray-700 dark:text-gray-300">
					{$i18n.t('Project ID')} <span class="text-red-500">*</span>
				</label>
				<input
					id="memory-create-project"
					type="text"
					bind:value={projectId}
					maxlength="256"
					placeholder="beleidsscan:GM0344:energietransitie"
					class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900
					       px-2 py-1.5 font-mono text-xs"
				/>
			</div>
		{/if}

		<div>
			<label for="memory-create-content" class="block text-xs font-medium mb-1 text-gray-700 dark:text-gray-300">
				{$i18n.t('Content')} <span class="text-red-500">*</span>
			</label>
			<textarea
				id="memory-create-content"
				bind:value={content}
				maxlength={CONTENT_MAX}
				rows={6}
				placeholder={$i18n.t('Full body — markdown allowed; this is what future chats recall.')}
				class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900
				       px-2 py-1.5 font-mono text-xs leading-snug resize-y"
				required
			></textarea>
		</div>

		{#if err}
			<div class="rounded-md bg-red-50 dark:bg-red-950/30 ring-1 ring-red-200 dark:ring-red-900
			            px-3 py-2 text-xs text-red-700 dark:text-red-300">
				{err}
			</div>
		{/if}

		<div class="flex justify-end gap-2 pt-1">
			<button
				type="button"
				class="px-3 py-1.5 rounded-lg text-sm
				       text-gray-700 dark:text-gray-300
				       hover:bg-gray-100 dark:hover:bg-gray-800 transition"
				on:click={() => (show = false)}
				disabled={saving}
			>
				{$i18n.t('Cancel')}
			</button>
			<button
				type="submit"
				class="px-3 py-1.5 rounded-lg text-sm font-medium
				       bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900
				       hover:bg-gray-800 dark:hover:bg-gray-200 transition
				       disabled:opacity-50 disabled:cursor-not-allowed"
				disabled={saving}
			>
				{saving ? $i18n.t('Saving…') : $i18n.t('Save')}
			</button>
		</div>
	</form>
</Modal>
