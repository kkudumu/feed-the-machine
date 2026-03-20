<script lang="ts">
	import KawaiiCard from '$lib/components/ui/KawaiiCard.svelte';
	import StatusBadge from '$lib/components/ui/StatusBadge.svelte';
	import PillButton from '$lib/components/ui/PillButton.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import StreamDrawer from '$lib/components/ui/StreamDrawer.svelte';
	import InboxFeed from '$lib/components/InboxFeed.svelte';
	import PlanView from '$lib/components/PlanView.svelte';
	import type { UnifiedTask, Plan } from '$lib/api';
	import { generatePlan, getPlan } from '$lib/api';
	type StatusBadgeStatus = 'pending' | 'planning' | 'approved' | 'executing' | 'complete' | 'failed';

	// Map arbitrary task status string to a valid StatusBadge value
	function taskStatusBadge(s: string): StatusBadgeStatus {
		const valid: StatusBadgeStatus[] = ['pending', 'planning', 'approved', 'executing', 'complete', 'failed'];
		return (valid.includes(s as StatusBadgeStatus) ? s : 'pending') as StatusBadgeStatus;
	}

	const API_BASE = 'http://localhost:8042';

	const sourceAccent: Record<string, 'blue' | 'green' | 'yellow' | 'coral'> = {
		jira:          'blue',
		freshservice:  'green',
		slack:         'yellow',
		gmail:         'coral'
	};

	let selectedTask: UnifiedTask | null = null;
	let currentPlan: Plan | null = null;
	let planLoading = false;
	let drawerOpen = false;
	let drawerLines: string[] = [];
	let auditEntries: { time: string; level: string; msg: string }[] = [];

	function addAudit(level: 'info' | 'warn' | 'success' | 'error', msg: string) {
		auditEntries = [
			...auditEntries,
			{ time: new Date().toLocaleTimeString('en-GB', { hour12: false }), level, msg }
		];
	}

	async function handleSelectTask(e: CustomEvent<UnifiedTask>) {
		selectedTask = e.detail;
		currentPlan = null;
		// Load existing plan for this task if one exists
		try {
			currentPlan = await getPlan(e.detail.id);
		} catch {
			// No plan yet — that's fine
		}
	}

	async function handleGeneratePlan(e: CustomEvent<UnifiedTask>) {
		selectedTask = e.detail;
		currentPlan = null;
		planLoading = true;
		drawerLines = [];
		drawerOpen = true;

		const task = e.detail;
		addAudit('info', `Plan generation started for: ${task.title}`);
		drawerLines = [...drawerLines, `[${new Date().toLocaleTimeString()}] Generate plan: ${task.title}`];

		// Use SSE stream for live output in the drawer
		try {
			const evtSource = new EventSource(`${API_BASE}/api/tasks/${task.id}/plan-stream`);

			evtSource.onmessage = (event) => {
				try {
					const msg = JSON.parse(event.data);
					if (msg.type === 'chunk') {
						drawerLines = [...drawerLines, msg.text.trimEnd()];
					} else if (msg.type === 'done') {
						currentPlan = msg.plan as Plan;
						planLoading = false;
						addAudit('success', `Plan ready: ${currentPlan.steps.length} steps`);
						drawerLines = [...drawerLines, `Plan ready — ${currentPlan.steps.length} steps generated.`];
						evtSource.close();
					} else if (msg.type === 'error') {
						addAudit('error', `Plan failed: ${msg.message}`);
						drawerLines = [...drawerLines, `Error: ${msg.message}`];
						planLoading = false;
						evtSource.close();
					}
				} catch {
					// Ignore malformed SSE frames
				}
			};

			evtSource.onerror = () => {
				planLoading = false;
				addAudit('warn', 'SSE stream closed unexpectedly');
				evtSource.close();
			};
		} catch (err) {
			// Fallback: direct POST without streaming
			try {
				const plan = await generatePlan(task.id);
				currentPlan = plan;
				addAudit('success', `Plan ready: ${plan.steps.length} steps`);
			} catch (genErr) {
				addAudit('error', `Plan generation failed: ${genErr}`);
			} finally {
				planLoading = false;
			}
		}
	}

	function handlePlanUpdated(e: CustomEvent<Plan>) {
		currentPlan = e.detail;
		addAudit('info', `Plan updated — status: ${e.detail.status}`);
	}
</script>

<!-- Three-column layout + bottom drawer -->
<div class="layout-grid">
	<!-- Left: Task Inbox -->
	<aside class="sidebar sidebar-left" aria-label="Task inbox">
		<div class="sidebar-header">
			<h2 class="sidebar-title">Inbox</h2>
		</div>
		<div class="sidebar-body">
			<InboxFeed
				selectedTaskId={selectedTask?.id ?? null}
				on:selectTask={handleSelectTask}
				on:generatePlan={handleGeneratePlan}
			/>
		</div>
	</aside>

	<!-- Center: Plan Viewer -->
	<section class="center-panel" aria-label="Plan viewer">
		{#if selectedTask}
			<div class="plan-viewer">
				<div class="plan-header">
					<div class="plan-header-top">
						<span class="plan-id">{selectedTask.source}:{selectedTask.source_id}</span>
						<StatusBadge status={taskStatusBadge(selectedTask.status)} />
					</div>
					<h1 class="plan-title">{selectedTask.title}</h1>
					{#if selectedTask.body}
						<p class="plan-body">{selectedTask.body}</p>
					{/if}
				</div>

				<KawaiiCard accent={sourceAccent[selectedTask.source] ?? 'green'}>
					<span slot="header" class="card-label">Execution Plan</span>

					<PlanView
						plan={currentPlan}
						loading={planLoading}
						on:planUpdated={handlePlanUpdated}
					/>

					<div slot="footer" class="plan-actions">
						<PillButton
							variant="primary"
							size="sm"
							disabled={planLoading}
							on:click={() => { if (selectedTask) handleGeneratePlan(new CustomEvent('generatePlan', { detail: selectedTask })); }}
						>
							{planLoading ? 'Generating…' : currentPlan ? 'Regenerate Plan' : 'Generate Plan'}
						</PillButton>
						{#if selectedTask.source_url}
							<PillButton variant="ghost" size="sm" on:click={() => window.open(selectedTask?.source_url ?? '', '_blank')}>
								Open Source
							</PillButton>
						{/if}
					</div>
				</KawaiiCard>
			</div>
		{:else}
			<EmptyState
				emoji="🗂️"
				title="Select a task"
				message="Choose a task from the inbox to view its plan."
			/>
		{/if}
	</section>

	<!-- Right: Audit Log -->
	<aside class="sidebar sidebar-right" aria-label="Audit log">
		<div class="sidebar-header">
			<h2 class="sidebar-title">Audit Log</h2>
			{#if auditEntries.length > 0}
				<span class="sidebar-count">{auditEntries.length}</span>
			{/if}
		</div>
		<div class="sidebar-body">
			{#if auditEntries.length === 0}
				<EmptyState
					emoji="📋"
					title="No events yet"
					message="Audit events will appear here."
				/>
			{:else}
				<div class="audit-list">
					{#each auditEntries as entry, i (i)}
						<div class="audit-entry audit-{entry.level}">
							<span class="audit-time">{entry.time}</span>
							<span class="audit-msg">{entry.msg}</span>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</aside>
</div>

<!-- Bottom drawer for streaming agent output -->
<StreamDrawer bind:open={drawerOpen} lines={drawerLines} />

<style>
	/* ─── Three-column layout ─── */
	.layout-grid {
		display: flex;
		flex: 1;
		height: calc(100vh - 57px - 36px); /* minus nav height minus drawer handle */
		overflow: hidden;
	}

	.sidebar {
		display: flex;
		flex-direction: column;
		background: var(--bg-sidebar);
		overflow: hidden;
		flex-shrink: 0;
	}

	.sidebar-left {
		width: 280px;
		border-right: 1px solid var(--border-card);
	}

	.sidebar-right {
		width: 320px;
		border-left: 1px solid var(--border-card);
	}

	.sidebar-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1rem 0.5rem;
		border-bottom: 1px solid var(--border-card);
		background: var(--bg-card);
		flex-shrink: 0;
	}

	.sidebar-title {
		font-size: 0.72rem;
		font-weight: 800;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-muted);
		margin: 0;
	}

	.sidebar-count {
		font-size: 0.68rem;
		font-weight: 800;
		background: var(--border-card);
		color: var(--text-muted);
		padding: 2px 7px;
		border-radius: 9999px;
	}

	.sidebar-body {
		flex: 1;
		overflow-y: auto;
		padding: 0.75rem;
	}

	.center-panel {
		flex: 1;
		overflow-y: auto;
		padding: 1.25rem;
		min-width: 0;
	}

	/* ─── Plan viewer ─── */
	.plan-viewer {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		max-width: 680px;
		margin: 0 auto;
		animation: fadeUp 0.3s ease-out both;
	}

	@keyframes fadeUp {
		from { opacity: 0; transform: translateY(8px); }
		to   { opacity: 1; transform: translateY(0); }
	}

	.plan-header {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.plan-header-top {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.plan-id {
		font-size: 0.75rem;
		font-weight: 800;
		letter-spacing: 0.06em;
		color: var(--text-muted);
		font-family: 'Menlo', monospace;
	}

	.plan-title {
		font-size: 1.25rem;
		font-weight: 800;
		color: var(--text-primary);
		line-height: 1.3;
	}

	.plan-body {
		font-size: 0.85rem;
		color: var(--text-secondary);
		line-height: 1.5;
		margin: 0;
		max-height: 100px;
		overflow-y: auto;
	}

	.card-label {
		font-size: 0.72rem;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
	}


	.plan-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	/* ─── Audit log ─── */
	.audit-list {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.audit-entry {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.4rem 0.5rem;
		border-radius: 8px;
		font-size: 0.72rem;
		border-left: 3px solid transparent;
		transition: background 0.1s;
	}

	.audit-entry:hover { background: rgba(76, 175, 80, 0.04); }

	.audit-info    { border-left-color: #66bb6a; }
	.audit-warn    { border-left-color: #ffd54f; background: rgba(255, 213, 79, 0.06); }
	.audit-success { border-left-color: #4caf50; background: rgba(76, 175, 80, 0.06); }
	.audit-error   { border-left-color: #ef5350; background: rgba(239, 83, 80, 0.06); }

	.audit-time {
		font-family: 'Menlo', monospace;
		font-size: 0.65rem;
		color: var(--text-muted);
	}

	.audit-msg {
		color: var(--text-secondary);
		font-weight: 600;
		line-height: 1.4;
	}

	/* ─── Mobile responsive ─── */
	@media (max-width: 768px) {
		.layout-grid {
			flex-direction: column;
			height: auto;
			overflow: visible;
		}

		.sidebar-left,
		.sidebar-right {
			width: 100%;
			border-right: none;
			border-left: none;
			border-bottom: 1px solid var(--border-card);
			max-height: 40vh;
		}
	}
</style>
