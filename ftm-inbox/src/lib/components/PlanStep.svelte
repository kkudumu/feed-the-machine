<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import PillButton from '$lib/components/ui/PillButton.svelte';
	import type { PlanStep as PlanStepType } from '$lib/api';

	export let step: PlanStepType;
	export let index: number;

	const dispatch = createEventDispatcher<{
		approve: { stepId: number };
		reject:  { stepId: number };
	}>();

	const riskColor: Record<string, string> = {
		low:    'risk-low',
		medium: 'risk-medium',
		high:   'risk-high'
	};

	const riskEmoji: Record<string, string> = {
		low:    '🟢',
		medium: '🟡',
		high:   '🔴'
	};

	const statusEmoji: Record<string, string> = {
		pending:   '⏳',
		approved:  '✅',
		rejected:  '❌',
		running:   '⚡',
		completed: '🎉',
		failed:    '💥'
	};

	$: isPending   = step.status === 'pending';
	$: isApproved  = step.status === 'approved';
	$: isCompleted = step.status === 'completed';
	$: isFailed    = step.status === 'failed';
</script>

<div
	class="plan-step"
	class:step-approved={isApproved}
	class:step-completed={isCompleted}
	class:step-failed={isFailed}
	role="listitem"
>
	<!-- Step number bubble -->
	<div class="step-num" aria-hidden="true">{index}</div>

	<!-- Main content -->
	<div class="step-content">
		<div class="step-top">
			<span class="step-title">{step.title}</span>
			<span class="step-status" title="Status: {step.status}">
				{statusEmoji[step.status] ?? '⏳'}
			</span>
		</div>

		<div class="step-meta">
			{#if step.target_system}
				<span class="meta-badge badge-system">{step.target_system}</span>
			{/if}
			<span class="meta-badge {riskColor[step.risk_level] ?? 'risk-low'}">
				{riskEmoji[step.risk_level] ?? '🟢'} {step.risk_level}
			</span>
			{#if step.approval_required}
				<span class="meta-badge badge-approval">approval required</span>
			{/if}
		</div>

		{#if step.method_primary}
			<div class="step-method">
				<span class="method-label">primary:</span>
				<code class="method-value">{step.method_primary}</code>
				{#if step.method_fallback}
					<span class="method-label">fallback:</span>
					<code class="method-value">{step.method_fallback}</code>
				{/if}
			</div>
		{/if}

		{#if step.rollback}
			<div class="step-rollback">
				<span class="rollback-label">↩</span>
				<span class="rollback-text">{step.rollback}</span>
			</div>
		{/if}

		{#if isPending}
			<div class="step-actions">
				<PillButton
					variant="primary"
					size="sm"
					on:click={() => dispatch('approve', { stepId: step.id })}
				>
					Approve
				</PillButton>
				<PillButton
					variant="danger"
					size="sm"
					on:click={() => dispatch('reject', { stepId: step.id })}
				>
					Reject
				</PillButton>
			</div>
		{/if}
	</div>
</div>

<style>
	.plan-step {
		display: flex;
		gap: 0.75rem;
		padding: 0.75rem;
		border-radius: 12px;
		background: var(--bg-secondary, #f8f9fa);
		border: 1.5px solid var(--border-card, #e0e0e0);
		transition:
			border-color 0.2s ease,
			background 0.2s ease,
			transform 0.25s cubic-bezier(0.68, -0.55, 0.265, 1.55);
	}

	.plan-step:hover {
		transform: translateY(-1px);
	}

	.step-approved {
		border-color: #a5d6a7;
		background: rgba(165, 214, 167, 0.10);
	}

	.step-completed {
		border-color: #81c784;
		background: rgba(129, 199, 132, 0.12);
		opacity: 0.85;
	}

	.step-failed {
		border-color: #ef9a9a;
		background: rgba(239, 154, 154, 0.10);
	}

	/* Step number bubble */
	.step-num {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 26px;
		height: 26px;
		border-radius: 9999px;
		background: var(--border-card, #e0e0e0);
		font-size: 0.7rem;
		font-weight: 800;
		color: var(--text-secondary, #555);
		flex-shrink: 0;
		margin-top: 2px;
	}

	.step-approved .step-num  { background: #c8e6c9; color: #1b5e20; }
	.step-completed .step-num { background: #a5d6a7; color: #1b5e20; }
	.step-failed .step-num    { background: #ffcdd2; color: #b71c1c; }

	/* Content */
	.step-content {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.step-top {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.step-title {
		font-size: 0.875rem;
		font-weight: 700;
		color: var(--text-primary, #222);
		line-height: 1.35;
		flex: 1;
	}

	.step-status {
		font-size: 0.9rem;
		flex-shrink: 0;
	}

	/* Meta badges */
	.step-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}

	.meta-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
		padding: 2px 8px;
		border-radius: 9999px;
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	.badge-system {
		background: rgba(66, 165, 245, 0.15);
		color: #1565c0;
		border: 1px solid rgba(66, 165, 245, 0.3);
	}

	.risk-low    { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
	.risk-medium { background: #fffde7; color: #f57f17; border: 1px solid #ffe082; }
	.risk-high   { background: #fce4ec; color: #c62828; border: 1px solid #ef9a9a; }

	.badge-approval {
		background: rgba(255, 152, 0, 0.12);
		color: #e65100;
		border: 1px solid rgba(255, 152, 0, 0.3);
	}

	/* Method row */
	.step-method {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.72rem;
	}

	.method-label {
		color: var(--text-muted, #888);
		font-weight: 600;
	}

	.method-value {
		background: var(--bg-card, #fff);
		border: 1px solid var(--border-card, #e0e0e0);
		border-radius: 4px;
		padding: 1px 5px;
		font-family: 'Menlo', monospace;
		font-size: 0.68rem;
		color: var(--text-secondary, #555);
	}

	/* Rollback */
	.step-rollback {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.7rem;
		color: var(--text-muted, #888);
	}

	.rollback-label { font-size: 0.8rem; }
	.rollback-text  { font-style: italic; }

	/* Actions */
	.step-actions {
		display: flex;
		gap: 0.4rem;
		margin-top: 0.25rem;
	}
</style>
