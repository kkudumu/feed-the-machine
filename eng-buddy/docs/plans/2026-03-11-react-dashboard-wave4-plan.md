# React Dashboard Wave 4: Theme Plumbing + Playbook Management

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire up broken theme/settings hydration so themes persist across refresh, and enhance PlaybooksView with draft editing, promote/delete actions, and execution history.

**Architecture:** Two independent tracks. Track A fixes the settings→Zustand→DOM pipeline (types, client functions, store extension, layout hydration). Track B adds playbook CRUD UI on top of existing backend endpoints + two new endpoints (PATCH draft, GET history). Both tracks share the api/types.ts and api/client.ts files but touch different sections.

**Tech Stack:** React 18, TypeScript, Zustand, React Query, CSS Modules, FastAPI (Python), PlaybookManager

---

## Track A: Theme Plumbing Fix

### Task 1: Add SettingsResponse type + client functions

**Files:**
- Modify: `dashboard/frontend/src/api/types.ts` (append after line 120)
- Modify: `dashboard/frontend/src/api/client.ts` (append new functions)

**Step 1: Write the failing test**

The test file already exists at `dashboard/frontend/src/api/__tests__/client-wave2.test.ts` and imports `fetchSettings` and `updateSettings` — but these functions don't exist in client.ts yet. First verify the test fails.

**Step 2: Run test to verify it fails**

Run: `cd dashboard/frontend && npx vitest run src/api/__tests__/client-wave2.test.ts 2>&1 | head -30`
Expected: FAIL — cannot resolve `fetchSettings` from `../client`

**Step 3: Add SettingsResponse to types.ts**

Append to `dashboard/frontend/src/api/types.ts`:

```typescript
export interface SettingsResponse {
  terminal: string
  macos_notifications: boolean
  theme: string
  mode: string
}
```

**Step 4: Add settings + playbook client functions to client.ts**

Add imports at top of `dashboard/frontend/src/api/client.ts`:

```typescript
import type { SettingsResponse } from './types'
```

Append to `dashboard/frontend/src/api/client.ts`:

```typescript
export async function fetchSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>('/api/settings')
}

export async function updateSettings(body: Partial<SettingsResponse>): Promise<SettingsResponse> {
  return request<SettingsResponse>('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchPollers(): Promise<import('./types').PollersResponse> {
  return request('/api/pollers/status')
}

export async function syncPoller(pollerId: string): Promise<{ status: string }> {
  return request(`/api/pollers/${pollerId}/sync`, { method: 'POST' })
}

export async function postRestart(): Promise<{ status: string }> {
  return request('/api/restart', { method: 'POST' })
}

export async function postDecision(
  entity: 'cards' | 'tasks',
  id: number,
  action: string,
  decision: string,
  reason?: string,
): Promise<{ card_id?: number; task_number?: number; action: string; decision: string; decision_event_id: number; action_step_id: number }> {
  return request(`/api/${entity}/${id}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, decision, reason }),
  })
}

export async function fetchPlaybooks(): Promise<{ playbooks: Array<{ id: string; name: string; trigger: string; confidence: number; steps: Array<{ summary: string; tool: string }>; executions: number }> }> {
  return request('/api/playbooks')
}

export async function fetchPlaybookDrafts(): Promise<{ drafts: Array<{ id: string; name: string; trigger: string; confidence: number; steps: Array<{ summary: string; tool: string }> }> }> {
  return request('/api/playbooks/drafts')
}

export async function executePlaybook(
  playbookId: string,
  ticketContext: Record<string, unknown>,
  approval: string,
): Promise<{ status: string }> {
  return request('/api/playbooks/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ playbook_id: playbookId, ticket_context: ticketContext, approval }),
  })
}
```

**Step 5: Run test to verify it passes**

Run: `cd dashboard/frontend && npx vitest run src/api/__tests__/client-wave2.test.ts 2>&1 | tail -10`
Expected: All 6 tests PASS

**Step 6: Commit**

```bash
git add dashboard/frontend/src/api/types.ts dashboard/frontend/src/api/client.ts
git commit -m "Add SettingsResponse type and missing client functions (settings, pollers, playbooks)"
```

---

### Task 2: Extend Zustand UI store with theme/mode state

**Files:**
- Modify: `dashboard/frontend/src/stores/ui.ts`
- Test: `dashboard/frontend/src/stores/__tests__/ui.test.ts` (existing)

**Step 1: Write the failing test**

Add to `dashboard/frontend/src/stores/__tests__/ui.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '../ui'

// ... existing tests ...

describe('theme/mode state', () => {
  beforeEach(() => useUIStore.setState(useUIStore.getInitialState()))

  it('has default theme neon-dreams and mode dark', () => {
    const state = useUIStore.getState()
    expect(state.theme).toBe('neon-dreams')
    expect(state.mode).toBe('dark')
  })

  it('setTheme updates theme', () => {
    useUIStore.getState().setTheme('midnight-ops')
    expect(useUIStore.getState().theme).toBe('midnight-ops')
  })

  it('toggleMode flips dark to light', () => {
    useUIStore.getState().toggleMode()
    expect(useUIStore.getState().mode).toBe('light')
  })

  it('hydrateSettings sets all fields and DOM attrs', () => {
    // Mock document.documentElement.dataset
    const store = useUIStore.getState()
    store.hydrateSettings({ terminal: 'Warp', theme: 'soft-kitty', mode: 'light', macos_notifications: true })
    const state = useUIStore.getState()
    expect(state.theme).toBe('soft-kitty')
    expect(state.mode).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('soft-kitty')
    expect(document.documentElement.dataset.mode).toBe('light')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd dashboard/frontend && npx vitest run src/stores/__tests__/ui.test.ts 2>&1 | tail -15`
Expected: FAIL — `theme`, `mode`, `setTheme`, `toggleMode`, `hydrateSettings` not in state

**Step 3: Extend ui.ts store**

Replace full content of `dashboard/frontend/src/stores/ui.ts`:

```typescript
import { create } from 'zustand'
import type { CardSource, SettingsResponse } from '../api/types'

export type ThemeName = 'neon-dreams' | 'midnight-ops' | 'soft-kitty'
export type ModeName = 'dark' | 'light'

interface UIState {
  activeSource: CardSource
  activeCardId: number | null
  expandedActions: Set<number>
  expandedPlanCards: Set<number>
  editingStep: { cardId: number; stepIndex: number } | null
  theme: ThemeName
  mode: ModeName
  setActiveSource: (source: CardSource) => void
  setActiveCard: (id: number | null) => void
  toggleExpandedActions: (id: number) => void
  togglePlanExpanded: (cardId: number) => void
  setEditingStep: (ref: { cardId: number; stepIndex: number } | null) => void
  setTheme: (theme: ThemeName) => void
  toggleMode: () => void
  hydrateSettings: (settings: SettingsResponse) => void
}

function applyThemeToDOM(theme: string, mode: string) {
  document.documentElement.dataset.theme = theme
  document.documentElement.dataset.mode = mode
}

export const useUIStore = create<UIState>()((set) => ({
  activeSource: 'all',
  activeCardId: null,
  expandedActions: new Set(),
  expandedPlanCards: new Set(),
  editingStep: null,
  theme: 'neon-dreams',
  mode: 'dark',

  setActiveSource: (source) => set({ activeSource: source }),

  setActiveCard: (id) => set({ activeCardId: id }),

  toggleExpandedActions: (id) =>
    set((state) => {
      const next = new Set(state.expandedActions)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { expandedActions: next }
    }),

  togglePlanExpanded: (cardId) =>
    set((state) => {
      const next = new Set(state.expandedPlanCards)
      if (next.has(cardId)) next.delete(cardId)
      else next.add(cardId)
      return { expandedPlanCards: next }
    }),

  setEditingStep: (ref) => set({ editingStep: ref }),

  setTheme: (theme) => {
    applyThemeToDOM(theme, useUIStore.getState().mode)
    set({ theme })
  },

  toggleMode: () =>
    set((state) => {
      const mode = state.mode === 'dark' ? 'light' : 'dark'
      applyThemeToDOM(state.theme, mode)
      return { mode }
    }),

  hydrateSettings: (settings) => {
    const theme = (settings.theme || 'neon-dreams') as ThemeName
    const mode = (settings.mode || 'dark') as ModeName
    applyThemeToDOM(theme, mode)
    set({ theme, mode })
  },
}))
```

**Step 4: Run test to verify it passes**

Run: `cd dashboard/frontend && npx vitest run src/stores/__tests__/ui.test.ts 2>&1 | tail -15`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/stores/ui.ts dashboard/frontend/src/stores/__tests__/ui.test.ts
git commit -m "Extend UI store with theme/mode state, DOM hydration, and settings sync"
```

---

### Task 3: Wire useSettings hydration into AppLayout

**Files:**
- Modify: `dashboard/frontend/src/layouts/AppLayout.tsx` (add useSettings call)

**Step 1: Add useSettings import and call**

In `dashboard/frontend/src/layouts/AppLayout.tsx`, add import:

```typescript
import { useSettings } from '../hooks/useSettings'
```

Inside `AppLayout()` function body (first line after function declaration), add:

```typescript
useSettings()  // hydrates theme/mode from server on mount
```

This is a one-liner — `useSettings` already fetches settings and calls `hydrateSettings` via its `useEffect`. No test needed for this wiring (the hook and store are already tested).

**Step 2: Verify the build compiles**

Run: `cd dashboard/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors (or only pre-existing ones)

**Step 3: Commit**

```bash
git add dashboard/frontend/src/layouts/AppLayout.tsx
git commit -m "Hydrate theme settings on app mount via useSettings in AppLayout"
```

---

### Task 4: Sync DOM attrs immediately in ThemePicker and ModeToggle

**Files:**
- Modify: `dashboard/frontend/src/features/header/ThemePicker.tsx`
- Modify: `dashboard/frontend/src/features/header/ModeToggle.tsx`

**Step 1: Verify ThemePicker already works**

Read ThemePicker.tsx — it calls `setTheme(value)` which now (after Task 2) calls `applyThemeToDOM`. Check that it imports `ThemeName` from the correct path.

Current import: `import type { ThemeName } from '../../stores/ui'` — this now resolves since Task 2 exports `ThemeName`. No change needed to ThemePicker.

**Step 2: Verify ModeToggle already works**

Read ModeToggle.tsx — it calls `toggleMode()` which now (after Task 2) calls `applyThemeToDOM`. No change needed.

**Step 3: Run full test suite to confirm no regressions**

Run: `cd dashboard/frontend && npx vitest run 2>&1 | tail -20`
Expected: All tests pass

**Step 4: Commit (if any fixes needed)**

Only commit if changes were required. Track A is complete.

---

## Track B: Playbook Management

### Task 5: Add playbook TypeScript types

**Files:**
- Modify: `dashboard/frontend/src/api/types.ts` (append playbook types)

**Step 1: Add playbook management types**

Append to `dashboard/frontend/src/api/types.ts`:

```typescript
export interface PlaybookStepDetail {
  number: number
  description: string
  tool: string
  tool_params: Record<string, unknown>
  requires_human: boolean
  notes: string
}

export interface PlaybookDetail {
  id: string
  name: string
  description: string
  trigger_keywords: string[]
  steps: PlaybookStepDetail[]
  confidence: number
  version: number
  executions: number
  source: string
  runbook_path: string
  related_links: Record<string, string>
}

export interface PlaybookRunStep {
  number: number
  description: string
  tool: string
  status: 'success' | 'failed' | 'skipped'
  output: string | null
  duration_ms: number | null
}

export interface PlaybookRun {
  id: string
  playbook_id: string
  started_at: string
  finished_at: string | null
  status: 'success' | 'failed' | 'partial' | 'running'
  steps: PlaybookRunStep[]
}

export interface PlaybookHistoryResponse {
  runs: PlaybookRun[]
}
```

**Step 2: Verify build compiles**

Run: `cd dashboard/frontend && npx tsc --noEmit 2>&1 | head -10`
Expected: No new errors

**Step 3: Commit**

```bash
git add dashboard/frontend/src/api/types.ts
git commit -m "Add playbook detail, run history, and draft edit TypeScript types"
```

---

### Task 6: Add playbook management client functions

**Files:**
- Modify: `dashboard/frontend/src/api/client.ts` (append functions)
- Create: `dashboard/frontend/src/api/__tests__/client-wave4.test.ts`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/api/__tests__/client-wave4.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchPlaybookDetail, updatePlaybookDraft, promotePlaybook, deletePlaybookDraft, fetchPlaybookHistory } from '../client'

const mockFetch = vi.fn()
global.fetch = mockFetch

beforeEach(() => mockFetch.mockReset())

describe('Wave 4 playbook client', () => {
  it('fetchPlaybookDetail calls GET /api/playbooks/:id', async () => {
    const mock = { id: 'abc', name: 'Test', steps: [] }
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mock) })
    const result = await fetchPlaybookDetail('abc')
    expect(mockFetch).toHaveBeenCalledWith('/api/playbooks/abc')
    expect(result.id).toBe('abc')
  })

  it('updatePlaybookDraft PATCHes /api/playbooks/drafts/:id', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
    await updatePlaybookDraft('abc', { steps: [] })
    expect(mockFetch).toHaveBeenCalledWith('/api/playbooks/drafts/abc', expect.objectContaining({ method: 'PATCH' }))
  })

  it('promotePlaybook POSTs /api/playbooks/:id/promote', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
    await promotePlaybook('abc')
    expect(mockFetch).toHaveBeenCalledWith('/api/playbooks/abc/promote', expect.objectContaining({ method: 'POST' }))
  })

  it('deletePlaybookDraft DELETEs /api/playbooks/drafts/:id', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
    await deletePlaybookDraft('abc')
    expect(mockFetch).toHaveBeenCalledWith('/api/playbooks/drafts/abc', expect.objectContaining({ method: 'DELETE' }))
  })

  it('fetchPlaybookHistory calls GET /api/playbooks/:id/history', async () => {
    const mock = { runs: [] }
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mock) })
    const result = await fetchPlaybookHistory('abc')
    expect(mockFetch).toHaveBeenCalledWith('/api/playbooks/abc/history')
    expect(result.runs).toEqual([])
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd dashboard/frontend && npx vitest run src/api/__tests__/client-wave4.test.ts 2>&1 | tail -15`
Expected: FAIL — functions don't exist

**Step 3: Add client functions**

Append to `dashboard/frontend/src/api/client.ts`:

```typescript
import type { PlaybookDetail, PlaybookHistoryResponse } from './types'

export async function fetchPlaybookDetail(playbookId: string): Promise<PlaybookDetail> {
  return request<PlaybookDetail>(`/api/playbooks/${playbookId}`)
}

export async function updatePlaybookDraft(
  playbookId: string,
  body: Partial<PlaybookDetail>,
): Promise<{ status: string }> {
  return request(`/api/playbooks/drafts/${playbookId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function promotePlaybook(playbookId: string): Promise<{ status: string }> {
  return request(`/api/playbooks/${playbookId}/promote`, { method: 'POST' })
}

export async function deletePlaybookDraft(playbookId: string): Promise<{ status: string }> {
  return request(`/api/playbooks/drafts/${playbookId}`, { method: 'DELETE' })
}

export async function fetchPlaybookHistory(playbookId: string): Promise<PlaybookHistoryResponse> {
  return request<PlaybookHistoryResponse>(`/api/playbooks/${playbookId}/history`)
}
```

Note: merge the new `PlaybookDetail, PlaybookHistoryResponse` import into the existing import from `./types` at the top of client.ts.

**Step 4: Run test to verify it passes**

Run: `cd dashboard/frontend && npx vitest run src/api/__tests__/client-wave4.test.ts 2>&1 | tail -10`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/api/client.ts dashboard/frontend/src/api/__tests__/client-wave4.test.ts
git commit -m "Add playbook detail, draft update, promote, delete, and history client functions"
```

---

### Task 7: Add backend PATCH draft + GET history endpoints

**Files:**
- Modify: `dashboard/server.py` (add 2 endpoints after existing playbook endpoints ~line 2098)

**Step 1: Add PATCH /api/playbooks/drafts/{playbook_id} endpoint**

Add after the `delete_draft_playbook` endpoint (around line 2098) in `dashboard/server.py`:

```python
@app.patch("/api/playbooks/drafts/{playbook_id}")
async def update_draft_playbook(playbook_id: str, body: dict = Body(...)):
    """Update a draft playbook's steps or metadata."""
    mgr = _get_playbook_manager()
    pb = mgr.get_draft(playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Draft not found")
    if "name" in body:
        pb.name = body["name"]
    if "description" in body:
        pb.description = body["description"]
    if "steps" in body:
        from bin.playbook_engine.models import PlaybookStep
        pb.steps = [PlaybookStep.from_dict(s) for s in body["steps"]]
    if "trigger_keywords" in body:
        pb.trigger_keywords = body["trigger_keywords"]
    mgr.save_draft(pb)
    return pb.to_dict()
```

**Step 2: Add GET /api/playbooks/{playbook_id}/history endpoint**

Add after the PATCH endpoint:

```python
@app.get("/api/playbooks/{playbook_id}/history")
async def get_playbook_history(playbook_id: str):
    """Get execution history for a playbook."""
    import sqlite3
    db_path = RUNTIME_DIR / "events.db"
    if not db_path.exists():
        return {"runs": []}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM events WHERE event_type = 'playbook_execution' AND json_extract(payload, '$.playbook_id') = ? ORDER BY timestamp DESC LIMIT 50",
        (playbook_id,),
    ).fetchall()
    conn.close()
    runs = []
    for row in rows:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        runs.append({
            "id": str(row["id"]),
            "playbook_id": playbook_id,
            "started_at": row["timestamp"],
            "finished_at": payload.get("finished_at"),
            "status": payload.get("status", "unknown"),
            "steps": payload.get("steps", []),
        })
    return {"runs": runs}
```

**Step 3: Verify server starts**

Run: `cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard && python -c "import server" 2>&1 | head -5`
Expected: No import errors

**Step 4: Commit**

```bash
git add dashboard/server.py
git commit -m "Add PATCH draft update and GET playbook execution history endpoints"
```

---

### Task 8: Build DraftEditor component

**Files:**
- Create: `dashboard/frontend/src/features/playbooks/DraftEditor.tsx`
- Create: `dashboard/frontend/src/features/playbooks/DraftEditor.module.css`

**Step 1: Create DraftEditor component**

Create `dashboard/frontend/src/features/playbooks/DraftEditor.tsx`:

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPlaybookDetail, updatePlaybookDraft, promotePlaybook, deletePlaybookDraft } from '../../api/client'
import { useToastStore } from '../../stores/toast'
import type { PlaybookStepDetail } from '../../api/types'
import styles from './DraftEditor.module.css'

interface Props {
  draftId: string
  onClose: () => void
}

export function DraftEditor({ draftId, onClose }: Props) {
  const queryClient = useQueryClient()
  const addToast = useToastStore((s) => s.addToast)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<Partial<PlaybookStepDetail>>({})

  const { data, isLoading } = useQuery({
    queryKey: ['playbook-detail', draftId],
    queryFn: () => fetchPlaybookDetail(draftId),
  })

  const updateMutation = useMutation({
    mutationFn: (steps: PlaybookStepDetail[]) => updatePlaybookDraft(draftId, { steps }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbook-detail', draftId] })
      queryClient.invalidateQueries({ queryKey: ['playbook-drafts'] })
      addToast('Draft updated', 'success')
    },
  })

  const promoteMutation = useMutation({
    mutationFn: () => promotePlaybook(draftId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbook-drafts'] })
      queryClient.invalidateQueries({ queryKey: ['playbooks'] })
      addToast('Playbook promoted', 'success')
      onClose()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePlaybookDraft(draftId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbook-drafts'] })
      addToast('Draft deleted', 'success')
      onClose()
    },
  })

  if (isLoading || !data) return <div className={styles.loading}>Loading draft...</div>

  const steps = data.steps

  const startEdit = (index: number) => {
    setEditingIndex(index)
    setEditForm(steps[index])
  }

  const saveEdit = () => {
    if (editingIndex === null) return
    const updated = [...steps]
    updated[editingIndex] = { ...updated[editingIndex], ...editForm }
    updateMutation.mutate(updated)
    setEditingIndex(null)
  }

  const deleteStep = (index: number) => {
    const updated = steps.filter((_, i) => i !== index).map((s, i) => ({ ...s, number: i + 1 }))
    updateMutation.mutate(updated)
  }

  const moveStep = (index: number, direction: -1 | 1) => {
    const target = index + direction
    if (target < 0 || target >= steps.length) return
    const updated = [...steps]
    ;[updated[index], updated[target]] = [updated[target], updated[index]]
    updateMutation.mutate(updated.map((s, i) => ({ ...s, number: i + 1 })))
  }

  return (
    <div className={styles.editor}>
      <div className={styles.header}>
        <h4 className={styles.title}>{data.name}</h4>
        <div className={styles.actions}>
          <button onClick={() => promoteMutation.mutate()} className={styles.promoteBtn} disabled={promoteMutation.isPending}>
            Promote
          </button>
          <button onClick={() => deleteMutation.mutate()} className={styles.deleteBtn} disabled={deleteMutation.isPending}>
            Delete
          </button>
          <button onClick={onClose} className={styles.closeBtn}>Close</button>
        </div>
      </div>

      {data.description && <p className={styles.description}>{data.description}</p>}

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>#</th>
            <th className={styles.th}>Description</th>
            <th className={styles.th}>Tool</th>
            <th className={styles.th}>Human?</th>
            <th className={styles.th}></th>
          </tr>
        </thead>
        <tbody>
          {steps.map((step, i) => (
            <tr key={i} className={styles.row}>
              {editingIndex === i ? (
                <>
                  <td className={styles.td}>{step.number}</td>
                  <td className={styles.td}>
                    <input
                      className={styles.input}
                      value={editForm.description ?? ''}
                      onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    />
                  </td>
                  <td className={styles.td}>
                    <input
                      className={styles.input}
                      value={editForm.tool ?? ''}
                      onChange={(e) => setEditForm({ ...editForm, tool: e.target.value })}
                    />
                  </td>
                  <td className={styles.td}>{step.requires_human ? 'Yes' : 'No'}</td>
                  <td className={styles.td}>
                    <button onClick={saveEdit} className={styles.saveBtn}>Save</button>
                    <button onClick={() => setEditingIndex(null)} className={styles.cancelBtn}>Cancel</button>
                  </td>
                </>
              ) : (
                <>
                  <td className={styles.td}>{step.number}</td>
                  <td className={styles.td}>{step.description}</td>
                  <td className={styles.tdTool}>{step.tool}</td>
                  <td className={styles.td}>{step.requires_human ? 'Yes' : 'No'}</td>
                  <td className={styles.td}>
                    <button onClick={() => startEdit(i)} className={styles.editBtn}>Edit</button>
                    <button onClick={() => moveStep(i, -1)} className={styles.moveBtn} disabled={i === 0}>Up</button>
                    <button onClick={() => moveStep(i, 1)} className={styles.moveBtn} disabled={i === steps.length - 1}>Dn</button>
                    <button onClick={() => deleteStep(i)} className={styles.deleteStepBtn}>X</button>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

**Step 2: Create DraftEditor styles**

Create `dashboard/frontend/src/features/playbooks/DraftEditor.module.css`:

```css
.editor { padding: 1rem; background: var(--surface); border: 1px solid var(--border-subtle); border-radius: var(--radius, 8px); margin-bottom: 0.75rem; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.title { font-family: var(--font-heading, var(--font)); font-size: 0.95rem; color: var(--text); margin: 0; }
.description { font-family: var(--font-mono); font-size: 0.7rem; color: var(--muted); margin: 0 0 0.75rem; }
.actions { display: flex; gap: 0.5rem; }
.loading { color: var(--muted); font-family: var(--font-mono); padding: 1rem; }

.table { width: 100%; border-collapse: collapse; font-family: var(--font-mono); font-size: 0.75rem; }
.th { text-align: left; padding: 0.3rem 0.5rem; color: var(--muted); border-bottom: 1px solid var(--border-subtle); font-size: 0.65rem; text-transform: uppercase; }
.td { padding: 0.3rem 0.5rem; color: var(--text); border-bottom: 1px solid var(--border-faint); }
.tdTool { padding: 0.3rem 0.5rem; color: var(--jira); border-bottom: 1px solid var(--border-faint); font-size: 0.65rem; }
.row:hover { background: var(--hover-bg); }

.input { width: 100%; font-family: var(--font-mono); font-size: 0.75rem; padding: 2px 6px; border: 1px solid var(--border-subtle); background: var(--card-bg); color: var(--text); border-radius: var(--radius-sm, 4px); }

.promoteBtn, .deleteBtn, .closeBtn, .editBtn, .saveBtn, .cancelBtn, .moveBtn, .deleteStepBtn {
  font-family: var(--font-mono); font-size: 0.65rem; padding: 2px 8px;
  border: 1px solid var(--border-subtle); background: transparent; color: var(--text);
  border-radius: var(--radius-sm, 4px); cursor: pointer;
}
.promoteBtn { border-color: var(--fresh); color: var(--fresh); }
.promoteBtn:hover { background: var(--hover-bg); }
.deleteBtn { border-color: var(--urgent); color: var(--urgent); }
.deleteBtn:hover { background: var(--hover-bg); }
.deleteStepBtn { border-color: var(--urgent); color: var(--urgent); }
.editBtn:hover, .saveBtn:hover, .cancelBtn:hover, .moveBtn:hover { background: var(--hover-bg); }
.moveBtn:disabled { opacity: 0.3; cursor: default; }
```

**Step 3: Verify build compiles**

Run: `cd dashboard/frontend && npx tsc --noEmit 2>&1 | head -10`
Expected: No new errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/features/playbooks/DraftEditor.tsx dashboard/frontend/src/features/playbooks/DraftEditor.module.css
git commit -m "Add DraftEditor component with inline step editing, reorder, and delete"
```

---

### Task 9: Build RunHistory component

**Files:**
- Create: `dashboard/frontend/src/features/playbooks/RunHistory.tsx`
- Create: `dashboard/frontend/src/features/playbooks/RunHistory.module.css`

**Step 1: Create RunHistory component**

Create `dashboard/frontend/src/features/playbooks/RunHistory.tsx`:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchPlaybookHistory } from '../../api/client'
import { Badge } from '../../components/Badge'
import type { PlaybookRun } from '../../api/types'
import styles from './RunHistory.module.css'

interface Props {
  playbookId: string
}

export function RunHistory({ playbookId }: Props) {
  const [expandedRun, setExpandedRun] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['playbook-history', playbookId],
    queryFn: () => fetchPlaybookHistory(playbookId),
  })

  if (isLoading) return <div className={styles.loading}>Loading history...</div>

  const runs = data?.runs ?? []
  if (runs.length === 0) return <div className={styles.empty}>No execution history</div>

  const statusVariant = (status: PlaybookRun['status']): 'fresh' | 'urgent' | 'warning' | 'muted' => {
    switch (status) {
      case 'success': return 'fresh'
      case 'failed': return 'urgent'
      case 'partial': return 'warning'
      default: return 'muted'
    }
  }

  return (
    <div className={styles.container}>
      {runs.map((run) => (
        <div key={run.id} className={styles.run}>
          <button
            className={styles.runHeader}
            onClick={() => setExpandedRun(expandedRun === run.id ? null : run.id)}
          >
            <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
            <span className={styles.date}>{new Date(run.started_at).toLocaleString()}</span>
            <span className={styles.stepCount}>{run.steps.length} steps</span>
            <span className={styles.chevron}>{expandedRun === run.id ? '\u25BC' : '\u25B6'}</span>
          </button>

          {expandedRun === run.id && (
            <div className={styles.steps}>
              {run.steps.map((step, i) => (
                <div key={i} className={styles.step}>
                  <span className={styles.stepNum}>{step.number}.</span>
                  <span className={styles.stepDesc}>{step.description}</span>
                  <span className={styles.stepTool}>{step.tool}</span>
                  <Badge variant={statusVariant(step.status as PlaybookRun['status'])}>{step.status}</Badge>
                  {step.duration_ms != null && (
                    <span className={styles.duration}>{(step.duration_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
```

**Step 2: Create RunHistory styles**

Create `dashboard/frontend/src/features/playbooks/RunHistory.module.css`:

```css
.container { margin-top: 0.5rem; }
.loading, .empty { color: var(--muted); font-family: var(--font-mono); font-size: 0.75rem; padding: 1rem; }

.run { border: 1px solid var(--border-faint); border-radius: var(--radius-sm, 4px); margin-bottom: 0.5rem; overflow: hidden; }

.runHeader {
  width: 100%; display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0.75rem;
  background: var(--card-bg); border: none; color: var(--text); cursor: pointer;
  font-family: var(--font-mono); font-size: 0.75rem; text-align: left;
}
.runHeader:hover { background: var(--hover-bg); }
.date { color: var(--muted); font-size: 0.7rem; }
.stepCount { color: var(--muted); font-size: 0.65rem; margin-left: auto; }
.chevron { color: var(--muted); font-size: 0.6rem; }

.steps { padding: 0.5rem 0.75rem; background: var(--surface); }
.step {
  display: flex; align-items: center; gap: 0.5rem; padding: 0.25rem 0;
  font-family: var(--font-mono); font-size: 0.7rem;
}
.stepNum { color: var(--muted); min-width: 20px; }
.stepDesc { color: var(--text); flex: 1; }
.stepTool { color: var(--jira); font-size: 0.6rem; }
.duration { color: var(--muted); font-size: 0.6rem; }
```

**Step 3: Verify build compiles**

Run: `cd dashboard/frontend && npx tsc --noEmit 2>&1 | head -10`
Expected: No new errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/features/playbooks/RunHistory.tsx dashboard/frontend/src/features/playbooks/RunHistory.module.css
git commit -m "Add RunHistory component with exftmble per-step execution details"
```

---

### Task 10: Rewrite PlaybooksView with tabs (Drafts / Published / History)

**Files:**
- Modify: `dashboard/frontend/src/features/playbooks/PlaybooksView.tsx`
- Modify: `dashboard/frontend/src/features/playbooks/PlaybooksView.module.css`

**Step 1: Rewrite PlaybooksView**

Replace `dashboard/frontend/src/features/playbooks/PlaybooksView.tsx` with:

```tsx
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchPlaybooks, fetchPlaybookDrafts, executePlaybook } from '../../api/client'
import { useToastStore } from '../../stores/toast'
import { DraftEditor } from './DraftEditor'
import { RunHistory } from './RunHistory'
import styles from './PlaybooksView.module.css'

type Tab = 'drafts' | 'published' | 'history'

interface PlaybookStep { summary: string; tool: string }
interface PlaybookDraft { id: string; name: string; trigger: string; confidence: number; steps: PlaybookStep[] }
interface PlaybookItem extends PlaybookDraft { executions: number }

export function PlaybooksView() {
  const queryClient = useQueryClient()
  const addToast = useToastStore((s) => s.addToast)
  const [tab, setTab] = useState<Tab>('drafts')
  const [expandedDraft, setExpandedDraft] = useState<string | null>(null)
  const [historyPlaybook, setHistoryPlaybook] = useState<string | null>(null)
  const [approvalText, setApprovalText] = useState<Record<string, string>>({})

  const { data: draftsData, isLoading: draftsLoading } = useQuery({
    queryKey: ['playbook-drafts'],
    queryFn: fetchPlaybookDrafts,
  })

  const { data: playbooksData, isLoading: playbooksLoading } = useQuery({
    queryKey: ['playbooks'],
    queryFn: fetchPlaybooks,
  })

  const drafts = (draftsData?.drafts ?? []) as PlaybookDraft[]
  const playbooks = (playbooksData?.playbooks ?? []) as PlaybookItem[]

  const handleExecute = async (playbookId: string) => {
    const approval = approvalText[playbookId] || 'approved'
    try {
      await executePlaybook(playbookId, {}, approval)
      queryClient.invalidateQueries({ queryKey: ['playbooks'] })
      addToast(`Playbook ${playbookId} executed`, 'success')
    } catch {
      addToast(`Failed to execute playbook ${playbookId}`, 'error')
    }
  }

  if (draftsLoading || playbooksLoading) return <div className={styles.loading}>Loading playbooks...</div>

  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>Playbooks</h2>

      <div className={styles.tabs}>
        <button className={`${styles.tab} ${tab === 'drafts' ? styles.tabActive : ''}`} onClick={() => setTab('drafts')}>
          Drafts ({drafts.length})
        </button>
        <button className={`${styles.tab} ${tab === 'published' ? styles.tabActive : ''}`} onClick={() => setTab('published')}>
          Published ({playbooks.length})
        </button>
        <button className={`${styles.tab} ${tab === 'history' ? styles.tabActive : ''}`} onClick={() => setTab('history')}>
          History
        </button>
      </div>

      {tab === 'drafts' && (
        <section className={styles.section}>
          {drafts.length === 0 && <div className={styles.empty}>No drafts</div>}
          {drafts.map((d) => (
            <div key={d.id}>
              {expandedDraft === d.id ? (
                <DraftEditor draftId={d.id} onClose={() => setExpandedDraft(null)} />
              ) : (
                <div className={styles.card} onClick={() => setExpandedDraft(d.id)}>
                  <div className={styles.cardHeader}>
                    <span className={styles.name}>{d.name}</span>
                    <span className={styles.confidence}>{Math.round(d.confidence * 100)}%</span>
                  </div>
                  <div className={styles.trigger}>Trigger: {d.trigger}</div>
                  <div className={styles.meta}>{d.steps.length} steps</div>
                </div>
              )}
            </div>
          ))}
        </section>
      )}

      {tab === 'published' && (
        <section className={styles.section}>
          {playbooks.length === 0 && <div className={styles.empty}>No published playbooks</div>}
          {playbooks.map((p) => (
            <div key={p.id} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.name}>{p.name}</span>
                <span className={styles.executions}>{p.executions} runs</span>
              </div>
              <div className={styles.trigger}>Trigger: {p.trigger}</div>
              <div className={styles.steps}>
                {p.steps.map((s, i) => (
                  <div key={i} className={styles.step}>
                    <span className={styles.stepNum}>{i + 1}.</span>
                    <span>{s.summary}</span>
                    <span className={styles.tool}>{s.tool}</span>
                  </div>
                ))}
              </div>
              <div className={styles.executeRow}>
                <input
                  type="text" placeholder="Approval text..."
                  value={approvalText[p.id] || ''}
                  onChange={(e) => setApprovalText({ ...approvalText, [p.id]: e.target.value })}
                  className={styles.approvalInput}
                />
                <button onClick={() => handleExecute(p.id)} className={styles.executeBtn}>Execute</button>
                <button onClick={() => { setHistoryPlaybook(p.id); setTab('history') }} className={styles.historyBtn}>History</button>
              </div>
            </div>
          ))}
        </section>
      )}

      {tab === 'history' && (
        <section className={styles.section}>
          {historyPlaybook ? (
            <>
              <div className={styles.historyHeader}>
                <span>History for: {playbooks.find(p => p.id === historyPlaybook)?.name ?? historyPlaybook}</span>
                <button onClick={() => setHistoryPlaybook(null)} className={styles.clearBtn}>Show all</button>
              </div>
              <RunHistory playbookId={historyPlaybook} />
            </>
          ) : playbooks.length === 0 ? (
            <div className={styles.empty}>No playbooks with history</div>
          ) : (
            playbooks.map((p) => (
              <div key={p.id} className={styles.historySection}>
                <h4 className={styles.historyTitle}>{p.name}</h4>
                <RunHistory playbookId={p.id} />
              </div>
            ))
          )}
        </section>
      )}
    </div>
  )
}
```

**Step 2: Update PlaybooksView styles**

Replace `dashboard/frontend/src/features/playbooks/PlaybooksView.module.css` with:

```css
.container { padding: 1rem; }
.heading { font-family: var(--font-heading, var(--font)); color: var(--text); font-size: 1.2rem; margin-bottom: 0.75rem; }
.section { margin-top: 0.75rem; }
.loading, .empty { color: var(--muted); font-family: var(--font-mono); padding: 2rem; }

.tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border-subtle); }
.tab {
  font-family: var(--font-mono); font-size: 0.75rem; padding: 0.5rem 1rem;
  border: none; background: transparent; color: var(--muted); cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
}
.tab:hover { color: var(--text); }
.tabActive { color: var(--text); border-bottom-color: var(--fresh); }

.card {
  background: var(--card-bg); border: 1px solid var(--border-subtle);
  border-radius: var(--radius, 8px); padding: 1rem; margin-bottom: 0.75rem; cursor: pointer;
}
.card:hover { border-color: var(--border-hover, var(--fresh)); }
.cardHeader { display: flex; justify-content: space-between; align-items: center; }
.name { font-size: 0.9rem; color: var(--text); font-weight: 600; }
.confidence { font-family: var(--font-mono); font-size: 0.7rem; color: var(--fresh); }
.executions { font-family: var(--font-mono); font-size: 0.7rem; color: var(--jira); }
.trigger { font-family: var(--font-mono); font-size: 0.7rem; color: var(--muted); margin-top: 0.25rem; }
.meta { font-family: var(--font-mono); font-size: 0.65rem; color: var(--muted); margin-top: 0.25rem; }
.steps { margin-top: 0.5rem; }
.step {
  display: flex; gap: 0.5rem; align-items: center;
  font-family: var(--font-mono); font-size: 0.75rem; color: var(--text);
  padding: 0.2rem 0;
}
.stepNum { color: var(--muted); min-width: 20px; }
.tool { font-size: 0.6rem; color: var(--jira); margin-left: auto; }

.executeRow { display: flex; gap: 0.5rem; margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid var(--border-faint); }
.approvalInput {
  flex: 1; font-family: var(--font-mono); font-size: 0.75rem; padding: 4px 8px;
  border: 1px solid var(--border-subtle); background: var(--surface); color: var(--text);
  border-radius: var(--radius-sm, 4px);
}
.executeBtn, .historyBtn {
  font-family: var(--font-mono); font-size: 0.75rem; padding: 4px 12px;
  border: 1px solid var(--fresh); background: transparent; color: var(--fresh);
  border-radius: var(--radius-sm, 4px); cursor: pointer;
}
.historyBtn { border-color: var(--jira); color: var(--jira); }
.executeBtn:hover, .historyBtn:hover { background: var(--hover-bg); }

.historyHeader { display: flex; justify-content: space-between; align-items: center; font-family: var(--font-mono); font-size: 0.75rem; color: var(--text); margin-bottom: 0.5rem; }
.clearBtn { font-family: var(--font-mono); font-size: 0.65rem; padding: 2px 8px; border: 1px solid var(--border-subtle); background: transparent; color: var(--muted); border-radius: var(--radius-sm, 4px); cursor: pointer; }
.clearBtn:hover { background: var(--hover-bg); }
.historySection { margin-bottom: 1.5rem; }
.historyTitle { font-family: var(--font-heading, var(--font)); font-size: 0.85rem; color: var(--text); margin: 0 0 0.5rem; }
```

**Step 3: Verify build compiles**

Run: `cd dashboard/frontend && npx tsc --noEmit 2>&1 | head -10`
Expected: No new errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/features/playbooks/PlaybooksView.tsx dashboard/frontend/src/features/playbooks/PlaybooksView.module.css
git commit -m "Rewrite PlaybooksView with tabs: drafts (exftmble editor), published, and history"
```

---

### Task 11: Full test suite + smoke test

**Files:** None (verification only)

**Step 1: Run full frontend test suite**

Run: `cd dashboard/frontend && npx vitest run 2>&1 | tail -30`
Expected: All tests pass

**Step 2: Verify TypeScript compiles clean**

Run: `cd dashboard/frontend && npx tsc --noEmit 2>&1`
Expected: No errors

**Step 3: Verify Vite builds**

Run: `cd dashboard/frontend && npx vite build 2>&1 | tail -10`
Expected: Build succeeds

**Step 4: Verify server.py imports cleanly**

Run: `cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard && python -c "import server; print('OK')" 2>&1`
Expected: `OK`

**Step 5: Final commit if any fixes needed**

Only if smoke test revealed issues to fix.
