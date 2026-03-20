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
