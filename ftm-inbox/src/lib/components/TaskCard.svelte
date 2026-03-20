<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { fly } from 'svelte/transition';
	import StatusBadge from './ui/StatusBadge.svelte';
	import PillButton from './ui/PillButton.svelte';
	import type { UnifiedTask } from '$lib/api';

	export let task: UnifiedTask;
	export let selected = false;

	const dispatch = createEventDispatcher<{
		select: UnifiedTask;
		generatePlan: UnifiedTask;
	}>();

	const sourceColors: Record<string, string> = {
		jira: '#bbdefb',
		freshservice: '#c8e6c9',
		slack: '#e1bee7',
		gmail: '#ffcdd2'
	};

	const sourceTextColors: Record<string, string> = {
		jira: '#0d47a1',
		freshservice: '#1b5e20',
		slack: '#4a148c',
		gmail: '#b71c1c'
	};

	function relativeTime(dateStr: string | null): string {
		if (!dateStr) return '';
		const now = Date.now();
		const then = new Date(dateStr).getTime();
		if (isNaN(then)) return '';
		const diff = Math.floor((now - then) / 1000);
		if (diff < 60) return 'just now';
		if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
		if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
		return `${Math.floor(diff / 86400)}d ago`;
	}

	function mapStatus(s: string): 'pending' | 'planning' | 'approved' | 'executing' | 'complete' | 'failed' {
		const map: Record<string, 'pending' | 'planning' | 'approved' | 'executing' | 'complete' | 'failed'> = {
			open: 'pending',
			pending: 'planning',
			resolved: 'complete',
			closed: 'complete',
		};
		return map[s] ?? 'pending';
	}

	const priorityIndicator: Record<string, string> = {
		low: '○',
		medium: '◑',
		high: '●',
		urgent: '◉'
	};
</script>

<button
	class="task-card"
	class:selected
	on:click={() => dispatch('select', task)}
	transition:fly={{ x: -20, duration: 200 }}
>
	<div class="card-top">
		<span
			class="source-badge"
			style="background: {sourceColors[task.source] ?? '#e0e0e0'}; color: {sourceTextColors[task.source] ?? '#333'}"
		>
			{task.source}
		</span>
		<span class="card-time">{relativeTime(task.ingested_at ?? task.created_at)}</span>
	</div>

	<p class="card-title">{task.title}</p>

	<div class="card-meta">
		{#if task.priority}
			<span class="priority" title={task.priority}>
				{priorityIndicator[task.priority] ?? '○'} {task.priority}
			</span>
		{/if}
		{#if task.assignee}
			<span class="assignee" title="Assignee: {task.assignee}">
				{task.assignee}
			</span>
		{/if}
	</div>

	<div class="card-bottom">
		<StatusBadge status={mapStatus(task.status)} />
		<PillButton
			variant="primary"
			size="sm"
			on:click|stopPropagation={() => dispatch('generatePlan', task)}
		>
			Generate Plan
		</PillButton>
	</div>
</button>

<style>
	.task-card {
		display: block;
		width: 100%;
		text-align: left;
		background: var(--bg-card);
		border: 2px solid var(--border-card);
		border-radius: 12px;
		padding: 0.65rem 0.75rem;
		cursor: pointer;
		transition:
			border-color 0.15s ease,
			box-shadow 0.15s ease,
			transform 0.15s cubic-bezier(0.68, -0.55, 0.265, 1.55);
		font-family: 'Nunito', sans-serif;
	}

	.task-card:hover {
		border-color: var(--accent-primary);
		transform: translateX(2px);
	}

	.task-card.selected {
		border-color: var(--accent-primary);
		box-shadow: var(--shadow-card-hover);
		background: var(--bg-secondary);
	}

	.card-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.3rem;
	}

	.source-badge {
		font-size: 0.65rem;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding: 2px 8px;
		border-radius: 9999px;
	}

	.card-time {
		font-size: 0.68rem;
		color: var(--text-muted);
	}

	.card-title {
		font-size: 0.8rem;
		font-weight: 700;
		color: var(--text-primary);
		margin: 0 0 0.3rem;
		line-height: 1.35;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.card-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.4rem;
		font-size: 0.68rem;
		color: var(--text-muted);
	}

	.priority {
		font-weight: 700;
	}

	.assignee {
		max-width: 120px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.card-bottom {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
</style>
