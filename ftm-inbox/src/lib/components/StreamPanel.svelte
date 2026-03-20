<script lang="ts">
	import { afterUpdate } from 'svelte';

	export let lines: string[] = [];
	export let progress: string = '';
	export let autoScroll = true;

	let container: HTMLDivElement;

	afterUpdate(() => {
		if (autoScroll && container) {
			container.scrollTop = container.scrollHeight;
		}
	});
</script>

<div class="stream-panel">
	{#if progress}
		<div class="progress-bar">{progress}</div>
	{/if}
	<div class="stream-output" bind:this={container}>
		{#each lines as line, i (i)}
			<div class="stream-line">{line}</div>
		{/each}
		{#if lines.length === 0}
			<div class="stream-empty">Waiting for output...</div>
		{/if}
	</div>
	<div class="stream-controls">
		<label class="scroll-toggle">
			<input type="checkbox" bind:checked={autoScroll} />
			<span>Auto-scroll</span>
		</label>
		<span class="line-count">{lines.length} lines</span>
	</div>
</div>

<style>
	.stream-panel {
		display: flex;
		flex-direction: column;
		height: 100%;
		font-family: 'Menlo', 'Courier New', monospace;
		font-size: 0.75rem;
	}

	.progress-bar {
		padding: 0.4rem 0.75rem;
		background: rgba(76, 175, 80, 0.1);
		border-bottom: 1px solid var(--border-card);
		font-weight: 700;
		color: var(--accent-primary);
		font-size: 0.7rem;
	}

	.stream-output {
		flex: 1;
		overflow-y: auto;
		padding: 0.5rem 0.75rem;
	}

	.stream-line {
		padding: 1px 0;
		color: var(--text-secondary);
		white-space: pre-wrap;
		word-break: break-all;
		line-height: 1.5;
	}

	.stream-empty {
		color: var(--text-muted);
		font-style: italic;
	}

	.stream-controls {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.3rem 0.75rem;
		border-top: 1px solid var(--border-card);
		font-size: 0.65rem;
		color: var(--text-muted);
	}

	.scroll-toggle {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		cursor: pointer;
	}

	.scroll-toggle input {
		margin: 0;
	}

	.line-count {
		font-variant-numeric: tabular-nums;
	}
</style>
