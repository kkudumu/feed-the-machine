<script lang="ts">
	import { onMount, onDestroy, createEventDispatcher } from 'svelte';
	import TaskCard from './TaskCard.svelte';
	import PillButton from './ui/PillButton.svelte';
	import EmptyState from './ui/EmptyState.svelte';
	import { fetchInbox, type UnifiedTask } from '$lib/api';

	export let selectedTaskId: number | null = null;

	const dispatch = createEventDispatcher<{
		selectTask: UnifiedTask;
		generatePlan: UnifiedTask;
	}>();

	const sources = ['all', 'jira', 'freshservice', 'slack', 'gmail'] as const;
	let activeSource: string = 'all';
	let tasks: UnifiedTask[] = [];
	let total = 0;
	let loading = true;
	let error = '';
	let interval: ReturnType<typeof setInterval>;

	async function loadTasks() {
		try {
			const res = await fetchInbox(activeSource === 'all' ? undefined : activeSource);
			tasks = res.tasks;
			total = res.total;
			error = '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load';
		} finally {
			loading = false;
		}
	}

	function switchSource(source: string) {
		activeSource = source;
		loading = true;
		loadTasks();
	}

	onMount(() => {
		loadTasks();
		interval = setInterval(loadTasks, 15000);
	});

	onDestroy(() => {
		if (interval) clearInterval(interval);
	});
</script>

<div class="inbox-feed">
	<!-- Source tabs -->
	<div class="source-tabs">
		{#each sources as source}
			<PillButton
				variant={activeSource === source ? 'primary' : 'ghost'}
				size="sm"
				on:click={() => switchSource(source)}
			>
				{source === 'all' ? 'All' : source.charAt(0).toUpperCase() + source.slice(1)}
			</PillButton>
		{/each}
	</div>

	<!-- Task count -->
	{#if !loading && tasks.length > 0}
		<div class="task-count">{total} task{total !== 1 ? 's' : ''}</div>
	{/if}

	<!-- Task list -->
	<div class="task-list">
		{#if loading}
			<div class="loading-placeholder">
				{#each Array(3) as _}
					<div class="skeleton-card"></div>
				{/each}
			</div>
		{:else if error}
			<EmptyState emoji="⚠️" title="Connection error" message={error} />
		{:else if tasks.length === 0}
			<EmptyState emoji="📭" title="No tasks yet" message="Enjoy the quiet! Tasks will appear when pollers find them." />
		{:else}
			{#each tasks as task (task.id)}
				<TaskCard
					{task}
					selected={selectedTaskId === task.id}
					on:select={(e) => dispatch('selectTask', e.detail)}
					on:generatePlan={(e) => dispatch('generatePlan', e.detail)}
				/>
			{/each}
		{/if}
	</div>
</div>

<style>
	.inbox-feed {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		height: 100%;
	}

	.source-tabs {
		display: flex;
		gap: 0.35rem;
		flex-wrap: wrap;
		padding-bottom: 0.25rem;
	}

	.task-count {
		font-size: 0.68rem;
		font-weight: 700;
		color: var(--text-muted);
		letter-spacing: 0.04em;
	}

	.task-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		flex: 1;
		overflow-y: auto;
	}

	.loading-placeholder {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.skeleton-card {
		height: 80px;
		background: var(--bg-secondary);
		border-radius: 12px;
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.4; }
		50% { opacity: 0.7; }
	}
</style>
