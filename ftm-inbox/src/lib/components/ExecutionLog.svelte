<script lang="ts">
	import type { AuditEntry } from '$lib/api';

	export let entries: AuditEntry[] = [];

	const levelColors: Record<string, string> = {
		info: '#66bb6a',
		warn: '#ffd54f',
		success: '#4caf50',
		error: '#ef5350'
	};

	function levelFromAction(entry: AuditEntry): string {
		const result = entry.result as Record<string, unknown>;
		if (result?.status === 'failed') return 'error';
		if (result?.status === 'completed') return 'success';
		return 'info';
	}

	function formatTime(dateStr: string): string {
		try {
			return new Date(dateStr).toLocaleTimeString('en-GB', { hour12: false });
		} catch {
			return dateStr;
		}
	}
</script>

<div class="exec-log">
	{#each entries as entry (entry.id)}
		{@const level = levelFromAction(entry)}
		<div class="log-entry" style="border-left-color: {levelColors[level] ?? '#66bb6a'}">
			<span class="log-time">{formatTime(entry.created_at)}</span>
			<span class="log-action">{entry.action_type}</span>
			<span class="log-target">{entry.target_object}</span>
		</div>
	{/each}
</div>

<style>
	.exec-log {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.log-entry {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		padding: 0.35rem 0.5rem;
		border-radius: 8px;
		font-size: 0.72rem;
		border-left: 3px solid #66bb6a;
		transition: background 0.1s;
	}

	.log-entry:hover {
		background: rgba(76, 175, 80, 0.04);
	}

	.log-time {
		font-family: 'Menlo', monospace;
		font-size: 0.65rem;
		color: var(--text-muted);
	}

	.log-action {
		font-weight: 700;
		color: var(--text-secondary);
		text-transform: uppercase;
		font-size: 0.6rem;
		letter-spacing: 0.05em;
	}

	.log-target {
		color: var(--text-primary);
		font-weight: 600;
		line-height: 1.4;
	}
</style>
