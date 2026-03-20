/**
 * API client for the FTM Inbox backend.
 */

const API_BASE = 'http://localhost:8042';

export interface UnifiedTask {
	id: number;
	source: string;
	source_id: string;
	title: string;
	body: string;
	status: string;
	priority: string;
	assignee: string | null;
	requester: string | null;
	created_at: string | null;
	updated_at: string | null;
	tags: string[];
	custom_fields: Record<string, unknown>;
	source_url: string | null;
	content_hash: string | null;
	ingested_at: string | null;
}

export interface InboxResponse {
	tasks: UnifiedTask[];
	total: number;
	page: number;
	per_page: number;
}

export async function fetchInbox(source?: string, page = 1): Promise<InboxResponse> {
	const params = new URLSearchParams({ page: String(page) });
	if (source && source !== 'all') params.set('source', source);
	const res = await fetch(`${API_BASE}/api/inbox?${params}`);
	if (!res.ok) throw new Error(`API error: ${res.status}`);
	return res.json();
}

export async function fetchSources(): Promise<{ name: string; count: number }[]> {
	const res = await fetch(`${API_BASE}/api/inbox/sources`);
	if (!res.ok) return [];
	const data = await res.json();
	return data.sources ?? [];
}

// ---------------------------------------------------------------------------
// Plan types
// ---------------------------------------------------------------------------

export interface PlanStep {
	id: number;
	title: string;
	target_system: string;
	method_primary: string;
	method_fallback: string;
	risk_level: string;
	approval_required: boolean;
	rollback: string;
	status: string;
}

export interface Plan {
	id: number;
	task_id: number;
	steps: PlanStep[];
	status: string;
	yaml_content: string;
	created_at: string | null;
	updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Plan API functions
// ---------------------------------------------------------------------------

export async function generatePlan(taskId: number): Promise<Plan> {
	const res = await fetch(`${API_BASE}/api/tasks/${taskId}/generate-plan`, {
		method: 'POST'
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail ?? `API error: ${res.status}`);
	}
	return res.json();
}

export async function getPlan(taskId: number): Promise<Plan | null> {
	const res = await fetch(`${API_BASE}/api/tasks/${taskId}/plan`);
	if (!res.ok) return null;
	const data = await res.json();
	// Backend returns { plan: null } when no plan exists
	if ('plan' in data && data.plan === null) return null;
	return data as Plan;
}

export async function approveStep(taskId: number, stepId: number): Promise<Plan> {
	const res = await fetch(`${API_BASE}/api/tasks/${taskId}/plan/steps/${stepId}/approve`, {
		method: 'POST'
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail ?? `API error: ${res.status}`);
	}
	return res.json();
}

export async function approveAllSteps(taskId: number): Promise<Plan> {
	const res = await fetch(`${API_BASE}/api/tasks/${taskId}/plan/approve-all`, {
		method: 'POST'
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail ?? `API error: ${res.status}`);
	}
	return res.json();
}
