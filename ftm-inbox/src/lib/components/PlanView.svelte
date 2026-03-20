<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import PlanStep from '$lib/components/PlanStep.svelte';
	import PillButton from '$lib/components/ui/PillButton.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import type { Plan } from '$lib/api';
	import { approveStep, approveAllSteps } from '$lib/api';

	export let plan: Plan | null = null;
	export let loading = false;

	const dispatch = createEventDispatcher<{
		planUpdated: Plan;
	}>();

	const statusLabel: Record<string, string> = {
		draft:     'Draft',
		approved:  'Approved',
		executing: 'Executing',
		completed: 'Completed',
		failed:    'Failed'
	};

	const statusColor: Record<string, string> = {
		draft:     'status-draft',
		approved:  'status-approved',
		executing: 'status-executing',
		completed: 'status-completed',
		failed:    'status-failed'
	};

	$: allLowRisk = plan?.steps.every(s => s.risk_level === 'low') ?? false;
	$: hasPendingSteps = plan?.steps.some(s => s.status === 'pending') ?? false;
	$: approveAllEnabled = hasPendingSteps && allLowRisk && plan?.status === 'draft';

	async function handleApproveStep(e: CustomEvent<{ stepId: number }>) {
		if (!plan) return;
		try {
			const updated = await approveStep(plan.task_id, e.detail.stepId);
			dispatch('planUpdated', updated);
		} catch (err) {
			console.error('Failed to approve step:', err);
		}
	}

	async function handleApproveAll() {
		if (!plan) return;
		try {
			const updated = await approveAllSteps(plan.task_id);
			dispatch('planUpdated', updated);
		} catch (err) {
			console.error('Failed to approve all steps:', err);
		}
	}
</script>

<div class="plan-view" aria-label="Execution plan">
	{#if loading}
		<div class="plan-loading">
			<span class="loading-spinner" aria-hidden="true">✨</span>
			<span>Generating plan…</span>
		</div>

	{:else if !plan || plan.steps.length === 0}
		<EmptyState
			emoji="📋"
			title="No plan generated yet"
			message="Click 'Generate Plan' on a task card to create an execution plan."
		/>

	{:else}
		<!-- Plan header -->
		<div class="plan-header">
			<div class="plan-header-row">
				<span class="steps-count">{plan.steps.length} step{plan.steps.length === 1 ? '' : 's'}</span>
				<span class="plan-status {statusColor[plan.status] ?? 'status-draft'}">
					{statusLabel[plan.status] ?? plan.status}
				</span>
			</div>

			{#if approveAllEnabled}
				<div class="plan-global-actions">
					<PillButton variant="primary" size="sm" on:click={handleApproveAll}>
						Approve All Low-Risk
					</PillButton>
				</div>
			{/if}
		</div>

		<!-- Step list -->
		<ol class="steps-list" role="list">
			{#each plan.steps as step, i (step.id)}
				<li class="steps-list-item">
					<PlanStep
						{step}
						index={i + 1}
						on:approve={handleApproveStep}
						on:reject
					/>
				</li>
			{/each}
		</ol>
	{/if}
</div>

<style>
	.plan-view {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	/* Loading state */
	.plan-loading {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		padding: 2rem;
		font-size: 0.875rem;
		color: var(--text-muted, #888);
		font-weight: 600;
	}

	.loading-spinner {
		font-size: 1.2rem;
		animation: spin 1.4s linear infinite;
	}

	@keyframes spin {
		from { transform: rotate(0deg); }
		to   { transform: rotate(360deg); }
	}

	/* Plan header */
	.plan-header {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.plan-header-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.steps-count {
		font-size: 0.72rem;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--text-muted, #888);
	}

	.plan-status {
		display: inline-flex;
		align-items: center;
		padding: 2px 10px;
		border-radius: 9999px;
		font-size: 0.65rem;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.status-draft     { background: #f5f5f5;  color: #616161; border: 1px solid #e0e0e0; }
	.status-approved  { background: #e8f5e9;  color: #2e7d32; border: 1px solid #a5d6a7; }
	.status-executing { background: #e3f2fd;  color: #1565c0; border: 1px solid #90caf9; }
	.status-completed { background: #f1f8e9;  color: #33691e; border: 1px solid #aed581; }
	.status-failed    { background: #fce4ec;  color: #c62828; border: 1px solid #ef9a9a; }

	.plan-global-actions {
		display: flex;
		gap: 0.4rem;
	}

	/* Steps list */
	.steps-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.steps-list-item {
		animation: bounceIn 0.35s cubic-bezier(0.68, -0.55, 0.265, 1.55) both;
	}

	.steps-list-item:nth-child(1)  { animation-delay: 0.04s; }
	.steps-list-item:nth-child(2)  { animation-delay: 0.08s; }
	.steps-list-item:nth-child(3)  { animation-delay: 0.12s; }
	.steps-list-item:nth-child(4)  { animation-delay: 0.16s; }
	.steps-list-item:nth-child(5)  { animation-delay: 0.20s; }
	.steps-list-item:nth-child(6)  { animation-delay: 0.24s; }
	.steps-list-item:nth-child(7)  { animation-delay: 0.28s; }
	.steps-list-item:nth-child(8)  { animation-delay: 0.32s; }

	@keyframes bounceIn {
		from { opacity: 0; transform: translateY(10px) scale(0.97); }
		to   { opacity: 1; transform: translateY(0) scale(1); }
	}
</style>
