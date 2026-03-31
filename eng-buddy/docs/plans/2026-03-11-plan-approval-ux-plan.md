# Wave 3: Plan Approval UX — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use plan-executor to implement this plan task-by-task.

**Goal:** Add inline plan approval UX to the React dashboard so users can review, approve/skip/edit steps, and dispatch execution to Warp terminal.

**Architecture:** Extend CardItem with a collapsible PlanView that fetches plan data via React Query, renders phased step accordions with risk-based auto-approval, and streams execution progress via SSE. All backend APIs already exist.

**Tech Stack:** React 19, TypeScript, Zustand, TanStack React Query, CSS Modules, existing SSE infrastructure

---

### Task 1: Add Plan TypeScript Types

**Files:**
- Modify: `dashboard/frontend/src/api/types.ts`

**Step 1: Add plan types to types.ts**

Add after the existing `CardSource` type (end of file):

```typescript
export type StepStatus = 'pending' | 'approved' | 'edited' | 'skipped' | 'completed' | 'failed';
export type StepRisk = 'low' | 'medium' | 'high';
export type PlanStatus = 'pending' | 'executing' | 'completed';

export interface PlanStep {
  index: number;
  summary: string;
  detail: string;
  action_type: 'mcp' | 'manual' | 'browser';
  tool: string;
  params: Record<string, unknown>;
  param_sources: Record<string, string>;
  draft_content: string | null;
  risk: StepRisk;
  status: StepStatus;
  output: string | null;
}

export interface PlanPhase {
  name: string;
  steps: PlanStep[];
}

export interface Plan {
  id: string;
  card_id: number;
  source: string;
  playbook_id: string;
  confidence: number;
  status: PlanStatus;
  created_at: string;
  executed_at: string | null;
  phases: PlanPhase[];
}

export interface PlanResponse {
  plan: Plan;
}

export interface StepUpdateResponse {
  step: PlanStep;
}

export interface ApproveRemainingResponse {
  approved_count: number;
  plan: Plan;
}

export interface ExecuteResponse {
  status: 'dispatched';
  steps: number;
  skipped: number[];
}

export interface RegenerateResponse {
  status: 'queued';
  feedback: string;
}
```

**Step 2: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add dashboard/frontend/src/api/types.ts
git commit -m "Add Plan, PlanStep, PlanPhase TypeScript types for Wave 3"
```

---

### Task 2: Add Plan API Client Functions

**Files:**
- Modify: `dashboard/frontend/src/api/client.ts`

**Step 1: Add plan API functions after existing exports**

```typescript
export async function fetchPlan(cardId: number): Promise<PlanResponse> {
  return request<PlanResponse>(`/api/cards/${cardId}/plan`);
}

export async function updateStep(
  cardId: number,
  stepIndex: number,
  body: { status?: string; draft_content?: string; feedback?: string },
): Promise<StepUpdateResponse> {
  return request<StepUpdateResponse>(`/api/cards/${cardId}/plan/steps/${stepIndex}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function approveRemaining(
  cardId: number,
  fromIndex?: number,
): Promise<ApproveRemainingResponse> {
  return request<ApproveRemainingResponse>(`/api/cards/${cardId}/plan/approve-remaining`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_index: fromIndex ?? 0 }),
  });
}

export async function executePlan(cardId: number): Promise<ExecuteResponse> {
  return request<ExecuteResponse>(`/api/cards/${cardId}/plan/execute`, { method: 'POST' });
}

export async function regeneratePlan(
  cardId: number,
  feedback: string,
): Promise<RegenerateResponse> {
  return request<RegenerateResponse>(`/api/cards/${cardId}/plan/regenerate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feedback }),
  });
}
```

**Step 2: Add imports for new types at top of client.ts**

Add `PlanResponse, StepUpdateResponse, ApproveRemainingResponse, ExecuteResponse, RegenerateResponse` to the import from `./types`.

**Step 3: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/api/client.ts
git commit -m "Add plan API client functions (fetch, update step, approve, execute, regenerate)"
```

---

### Task 3: Add usePlan React Query Hook

**Files:**
- Create: `dashboard/frontend/src/hooks/usePlan.ts`

**Step 1: Create the hook file**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  approveRemaining,
  executePlan,
  fetchPlan,
  regeneratePlan,
  updateStep,
} from '../api/client';

export function usePlan(cardId: number | null) {
  return useQuery({
    queryKey: ['plan', cardId],
    queryFn: () => fetchPlan(cardId!),
    enabled: cardId !== null,
    retry: false,
  });
}

export function useUpdateStep(cardId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { stepIndex: number; status?: string; draft_content?: string; feedback?: string }) =>
      updateStep(cardId, args.stepIndex, args),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plan', cardId] }),
  });
}

export function useApproveRemaining(cardId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fromIndex?: number) => approveRemaining(cardId, fromIndex),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plan', cardId] }),
  });
}

export function useExecutePlan(cardId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => executePlan(cardId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plan', cardId] }),
  });
}

export function useRegeneratePlan(cardId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (feedback: string) => regeneratePlan(cardId, feedback),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plan', cardId] }),
  });
}
```

**Step 2: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add dashboard/frontend/src/hooks/usePlan.ts
git commit -m "Add usePlan React Query hooks for plan CRUD operations"
```

---

### Task 4: Extend Zustand Store for Plan UI State

**Files:**
- Modify: `dashboard/frontend/src/stores/ui.ts`

**Step 1: Add plan-related state**

Add to the store interface and initial state:

```typescript
// Add to interface
expandedPlanCards: Set<number>;
editingStep: { cardId: number; stepIndex: number } | null;
togglePlanExpanded: (cardId: number) => void;
setEditingStep: (step: { cardId: number; stepIndex: number } | null) => void;
```

Add to `create()`:

```typescript
expandedPlanCards: new Set(),
editingStep: null,
togglePlanExpanded: (cardId) =>
  set((s) => {
    const next = new Set(s.expandedPlanCards);
    if (next.has(cardId)) next.delete(cardId);
    else next.add(cardId);
    return { expandedPlanCards: next };
  }),
setEditingStep: (step) => set({ editingStep: step }),
```

**Step 2: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add dashboard/frontend/src/stores/ui.ts
git commit -m "Add expandedPlanCards and editingStep to Zustand UI store"
```

---

### Task 5: Build StepRow Component

**Files:**
- Create: `dashboard/frontend/src/features/plan/StepRow.tsx`
- Create: `dashboard/frontend/src/features/plan/StepRow.module.css`

**Step 1: Create StepRow.module.css**

```css
.row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  transition: background 0.15s ease;
}

.row:hover {
  background: var(--bg-elevated);
}

.autoApproved {
  opacity: 0.7;
}

.autoApproved:hover {
  opacity: 0.85;
}

.pending {
  border-left: 2px solid var(--accent-coral);
  padding-left: calc(0.75rem - 2px);
}

.failed {
  background: color-mix(in srgb, var(--accent-coral) 10%, transparent);
}

.statusIcon {
  flex-shrink: 0;
  width: 1.25rem;
  height: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  margin-top: 0.1rem;
}

.body {
  flex: 1;
  min-width: 0;
}

.summary {
  font-size: 0.85rem;
  color: var(--text-primary);
  line-height: 1.4;
}

.detail {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

.controls {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}

.controlBtn {
  padding: 0.2rem 0.5rem;
  font-size: 0.7rem;
  border-radius: 4px;
  border: 1px solid var(--bg-elevated);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.controlBtn:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.approveBtn:hover {
  border-color: var(--accent-mint);
  color: var(--accent-mint);
}

.skipBtn:hover {
  border-color: var(--text-muted);
}

.editBtn:hover {
  border-color: var(--accent-blue);
  color: var(--accent-blue);
}

.spinner {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

**Step 2: Create StepRow.tsx**

```tsx
import { PlanStep } from '../../api/types';
import { Badge } from '../../components/Badge';
import styles from './StepRow.module.css';

interface StepRowProps {
  step: PlanStep;
  onApprove: () => void;
  onSkip: () => void;
  onEdit: () => void;
}

const STATUS_ICONS: Record<string, string> = {
  pending: '\u25CF',     // ●
  approved: '\u2713',    // ✓
  edited: '\u270E',      // ✎
  skipped: '\u2298',     // ⊘
  completed: '\u2714',   // ✔
  failed: '\u2717',      // ✗
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'var(--accent-coral)',
  approved: 'var(--accent-mint)',
  edited: 'var(--accent-blue)',
  skipped: 'var(--text-muted)',
  completed: 'var(--accent-mint)',
  failed: 'var(--accent-coral)',
};

const RISK_BADGE: Record<string, 'mint' | 'coral' | undefined> = {
  low: undefined,
  medium: 'mint',
  high: 'coral',
};

function isAutoApproved(step: PlanStep): boolean {
  return step.risk !== 'high' && step.status === 'approved';
}

export function StepRow({ step, onApprove, onSkip, onEdit }: StepRowProps) {
  const auto = isAutoApproved(step);
  const showControls = step.risk === 'high' && step.status === 'pending';
  const isRunning = step.status === 'approved' && step.output === null;

  const rowClass = [
    styles.row,
    auto ? styles.autoApproved : '',
    step.status === 'pending' && step.risk === 'high' ? styles.pending : '',
    step.status === 'failed' ? styles.failed : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={rowClass}>
      <span
        className={`${styles.statusIcon} ${step.status === 'completed' ? '' : ''}`}
        style={{ color: STATUS_COLORS[step.status] }}
      >
        {STATUS_ICONS[step.status] ?? '?'}
      </span>
      <div className={styles.body}>
        <div className={styles.summary}>
          {step.summary}
          {RISK_BADGE[step.risk] && (
            <>
              {' '}
              <Badge color={RISK_BADGE[step.risk]!}>{step.risk}</Badge>
            </>
          )}
        </div>
        {step.detail && step.detail !== step.summary && (
          <div className={styles.detail}>{step.detail}</div>
        )}
      </div>
      {showControls && (
        <div className={styles.controls}>
          <button className={`${styles.controlBtn} ${styles.approveBtn}`} onClick={onApprove}>
            Approve
          </button>
          <button className={`${styles.controlBtn} ${styles.skipBtn}`} onClick={onSkip}>
            Skip
          </button>
          <button className={`${styles.controlBtn} ${styles.editBtn}`} onClick={onEdit}>
            Edit
          </button>
        </div>
      )}
    </div>
  );
}
```

**Step 3: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/features/plan/
git commit -m "Add StepRow component with risk badges and approval controls"
```

---

### Task 6: Build StepEditor Component

**Files:**
- Create: `dashboard/frontend/src/features/plan/StepEditor.tsx`
- Create: `dashboard/frontend/src/features/plan/StepEditor.module.css`

**Step 1: Create StepEditor.module.css**

```css
.editor {
  padding: 0.5rem 0.75rem 0.5rem 2.75rem;
  animation: fadeUp 0.2s ease-out both;
}

.textarea {
  width: 100%;
  min-height: 3.5rem;
  padding: 0.5rem;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--text-primary);
  background: var(--bg-deep);
  border: 1px solid var(--bg-elevated);
  border-radius: 6px;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s ease;
}

.textarea:focus {
  border-color: var(--accent-blue);
}

.actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.35rem;
}

.learningChip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.35rem;
  padding: 0.2rem 0.6rem;
  font-size: 0.7rem;
  color: var(--accent-blue);
  background: color-mix(in srgb, var(--accent-blue) 12%, transparent);
  border-radius: 99px;
  animation: fadeUp 0.3s ease-out both;
}

.learningIcon {
  cursor: pointer;
  font-size: 0.75rem;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

**Step 2: Create StepEditor.tsx**

```tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import { PlanStep } from '../../api/types';
import { Button } from '../../components/Button';
import styles from './StepEditor.module.css';

interface StepEditorProps {
  step: PlanStep;
  isRegenerating: boolean;
  learningText: string | null;
  onRegenerate: (feedback: string) => void;
  onCancel: () => void;
}

export function StepEditor({ step, isRegenerating, learningText, onRegenerate, onCancel }: StepEditorProps) {
  const [feedback, setFeedback] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [chipCollapsed, setChipCollapsed] = useState(false);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!learningText) return;
    const timer = setTimeout(() => setChipCollapsed(true), 10000);
    return () => clearTimeout(timer);
  }, [learningText]);

  const handleRegenerate = useCallback(() => {
    if (!feedback.trim()) return;
    onRegenerate(feedback.trim());
  }, [feedback, onRegenerate]);

  return (
    <div className={styles.editor}>
      {step.draft_content && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
          Current: {step.draft_content}
        </div>
      )}
      <textarea
        ref={textareaRef}
        className={styles.textarea}
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        placeholder="Describe what to change..."
        disabled={isRegenerating}
      />
      <div className={styles.actions}>
        <Button
          label={isRegenerating ? 'Regenerating...' : 'Regenerate'}
          variant="mint"
          onClick={handleRegenerate}
          disabled={isRegenerating || !feedback.trim()}
        />
        <Button label="Cancel" variant="ghost" onClick={onCancel} disabled={isRegenerating} />
      </div>
      {learningText && !chipCollapsed && (
        <div className={styles.learningChip}>
          <span>Learned: {learningText}</span>
        </div>
      )}
      {learningText && chipCollapsed && (
        <span
          className={styles.learningIcon}
          onClick={() => setChipCollapsed(false)}
          title={`Learned: ${learningText}`}
          style={{ color: 'var(--accent-blue)', cursor: 'pointer' }}
        >
          &#x1F4A1;
        </span>
      )}
    </div>
  );
}
```

**Step 3: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/features/plan/StepEditor.tsx dashboard/frontend/src/features/plan/StepEditor.module.css
git commit -m "Add StepEditor component with regeneration and learning chip"
```

---

### Task 7: Build PhaseAccordion Component

**Files:**
- Create: `dashboard/frontend/src/features/plan/PhaseAccordion.tsx`
- Create: `dashboard/frontend/src/features/plan/PhaseAccordion.module.css`

**Step 1: Create PhaseAccordion.module.css**

```css
.phase {
  border-radius: 6px;
  overflow: hidden;
}

.phaseHeader {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  user-select: none;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  transition: color 0.15s ease;
}

.phaseHeader:hover {
  color: var(--text-primary);
}

.chevron {
  transition: transform 0.2s ease;
  font-size: 0.65rem;
}

.chevronOpen {
  transform: rotate(90deg);
}

.phaseName {
  flex: 1;
}

.stepCount {
  font-size: 0.65rem;
  opacity: 0.7;
}

.steps {
  overflow: hidden;
  transition: max-height 0.25s ease-out;
}

.stepsOpen {
  max-height: 2000px;
}

.stepsClosed {
  max-height: 0;
}
```

**Step 2: Create PhaseAccordion.tsx**

```tsx
import { useState } from 'react';
import { PlanPhase, PlanStep } from '../../api/types';
import { StepRow } from './StepRow';
import styles from './PhaseAccordion.module.css';

interface PhaseAccordionProps {
  phase: PlanPhase;
  editingStepIndex: number | null;
  onApprove: (stepIndex: number) => void;
  onSkip: (stepIndex: number) => void;
  onEdit: (stepIndex: number) => void;
  renderEditor: (step: PlanStep) => React.ReactNode;
}

export function PhaseAccordion({
  phase,
  editingStepIndex,
  onApprove,
  onSkip,
  onEdit,
  renderEditor,
}: PhaseAccordionProps) {
  const [open, setOpen] = useState(true);

  const doneCount = phase.steps.filter(
    (s) => s.status === 'completed' || s.status === 'approved' || s.status === 'edited',
  ).length;

  return (
    <div className={styles.phase}>
      <div className={styles.phaseHeader} onClick={() => setOpen(!open)}>
        <span className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}>&#x25B6;</span>
        <span className={styles.phaseName}>{phase.name}</span>
        <span className={styles.stepCount}>
          {doneCount}/{phase.steps.length}
        </span>
      </div>
      <div className={`${styles.steps} ${open ? styles.stepsOpen : styles.stepsClosed}`}>
        {phase.steps.map((step) => (
          <div key={step.index}>
            <StepRow
              step={step}
              onApprove={() => onApprove(step.index)}
              onSkip={() => onSkip(step.index)}
              onEdit={() => onEdit(step.index)}
            />
            {editingStepIndex === step.index && renderEditor(step)}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 3: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/features/plan/PhaseAccordion.tsx dashboard/frontend/src/features/plan/PhaseAccordion.module.css
git commit -m "Add PhaseAccordion component with collapsible step list"
```

---

### Task 8: Build PlanView Container Component

**Files:**
- Create: `dashboard/frontend/src/features/plan/PlanView.tsx`
- Create: `dashboard/frontend/src/features/plan/PlanView.module.css`

**Step 1: Create PlanView.module.css**

```css
.container {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--bg-surface);
  border-radius: 8px;
  border-left: 3px solid var(--accent-mint);
  animation: fadeUp 0.3s ease-out both;
}

.needsAttention {
  border-left-color: var(--accent-coral);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.headerLeft {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.title {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--text-primary);
}

.confidence {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.headerControls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.phases {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.footer {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--bg-elevated);
}

.progressBar {
  flex: 1;
  height: 4px;
  background: var(--bg-elevated);
  border-radius: 2px;
  overflow: hidden;
}

.progressFill {
  height: 100%;
  background: var(--accent-mint);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progressLabel {
  font-size: 0.7rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.completedBanner {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--accent-mint);
}

.errorBanner {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--accent-coral);
}

.loading {
  padding: 1rem;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-muted);
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

**Step 2: Create PlanView.tsx**

```tsx
import { useCallback, useState } from 'react';
import { PlanStep } from '../../api/types';
import { Button } from '../../components/Button';
import { useApproveRemaining, useExecutePlan, usePlan, useUpdateStep } from '../../hooks/usePlan';
import { useUIStore } from '../../stores/ui';
import { PhaseAccordion } from './PhaseAccordion';
import { StepEditor } from './StepEditor';
import styles from './PlanView.module.css';

interface PlanViewProps {
  cardId: number;
}

export function PlanView({ cardId }: PlanViewProps) {
  const { data, isLoading, error } = usePlan(cardId);
  const updateStep = useUpdateStep(cardId);
  const approveAll = useApproveRemaining(cardId);
  const execute = useExecutePlan(cardId);
  const { editingStep, setEditingStep } = useUIStore();
  const [learnings, setLearnings] = useState<Record<number, string>>({});

  const plan = data?.plan;

  const handleApprove = useCallback(
    (stepIndex: number) => {
      updateStep.mutate({ stepIndex, status: 'approved' });
    },
    [updateStep],
  );

  const handleSkip = useCallback(
    (stepIndex: number) => {
      updateStep.mutate({ stepIndex, status: 'skipped' });
    },
    [updateStep],
  );

  const handleEdit = useCallback(
    (stepIndex: number) => {
      setEditingStep({ cardId, stepIndex });
    },
    [cardId, setEditingStep],
  );

  const handleRegenerate = useCallback(
    (stepIndex: number, feedback: string) => {
      updateStep.mutate(
        { stepIndex, feedback },
        {
          onSuccess: () => {
            setLearnings((prev) => ({ ...prev, [stepIndex]: feedback }));
            setEditingStep(null);
          },
        },
      );
    },
    [updateStep, setEditingStep],
  );

  const handleApproveAll = useCallback(() => {
    approveAll.mutate(0);
  }, [approveAll]);

  const handleExecute = useCallback(() => {
    execute.mutate();
  }, [execute]);

  if (isLoading) return <div className={styles.loading}>Loading plan...</div>;
  if (error || !plan) return null;

  const allSteps = plan.phases.flatMap((p) => p.steps);
  const pendingCount = allSteps.filter((s) => s.status === 'pending' && s.risk === 'high').length;
  const completedCount = allSteps.filter((s) => s.status === 'completed').length;
  const totalSteps = allSteps.length;
  const canExecute = pendingCount === 0 && plan.status === 'pending';
  const isExecuting = plan.status === 'executing';
  const isCompleted = plan.status === 'completed';
  const failedSteps = allSteps.filter((s) => s.status === 'failed');

  return (
    <div className={`${styles.container} ${pendingCount > 0 ? styles.needsAttention : ''}`}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.title}>Plan</span>
          <span className={styles.confidence}>{Math.round(plan.confidence * 100)}% confidence</span>
        </div>
        <div className={styles.headerControls}>
          {pendingCount > 0 && (
            <Button
              label={`Approve All (${pendingCount})`}
              variant="mint"
              onClick={handleApproveAll}
              disabled={approveAll.isPending}
            />
          )}
        </div>
      </div>

      <div className={styles.phases}>
        {plan.phases.map((phase) => (
          <PhaseAccordion
            key={phase.name}
            phase={phase}
            editingStepIndex={
              editingStep?.cardId === cardId ? editingStep.stepIndex : null
            }
            onApprove={handleApprove}
            onSkip={handleSkip}
            onEdit={handleEdit}
            renderEditor={(step: PlanStep) => (
              <StepEditor
                step={step}
                isRegenerating={updateStep.isPending}
                learningText={learnings[step.index] ?? null}
                onRegenerate={(fb) => handleRegenerate(step.index, fb)}
                onCancel={() => setEditingStep(null)}
              />
            )}
          />
        ))}
      </div>

      <div className={styles.footer}>
        {isCompleted && failedSteps.length === 0 && (
          <span className={styles.completedBanner}>Completed &#x2714;</span>
        )}
        {isCompleted && failedSteps.length > 0 && (
          <span className={styles.errorBanner}>
            Completed with {failedSteps.length} error{failedSteps.length > 1 ? 's' : ''}
          </span>
        )}
        {!isCompleted && (
          <>
            <Button
              label={
                isExecuting
                  ? 'Executing...'
                  : canExecute
                    ? `Execute (${totalSteps - allSteps.filter((s) => s.status === 'skipped').length} steps)`
                    : `${pendingCount} steps need approval`
              }
              variant={canExecute ? 'mint' : 'ghost'}
              onClick={handleExecute}
              disabled={!canExecute || execute.isPending}
            />
            {(isExecuting || completedCount > 0) && (
              <>
                <div className={styles.progressBar}>
                  <div
                    className={styles.progressFill}
                    style={{ width: `${(completedCount / totalSteps) * 100}%` }}
                  />
                </div>
                <span className={styles.progressLabel}>
                  {completedCount}/{totalSteps}
                </span>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
```

**Step 3: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/features/plan/PlanView.tsx dashboard/frontend/src/features/plan/PlanView.module.css
git commit -m "Add PlanView container with approval flow, execution, and progress bar"
```

---

### Task 9: Integrate PlanView into CardItem

**Files:**
- Modify: `dashboard/frontend/src/features/inbox/CardItem.tsx`

**Step 1: Add plan toggle and PlanView rendering**

Import PlanView and the UI store at the top:

```typescript
import { useUIStore } from '../../stores/ui';
import { PlanView } from '../plan/PlanView';
```

Add inside the component, before the return:

```typescript
const { expandedPlanCards, togglePlanExpanded } = useUIStore();
const showPlan = expandedPlanCards.has(card.id);
```

Add a "Plan" toggle button after the existing card content (after `draft_response` section, before the closing `</div>`):

```tsx
{card.proposed_actions?.some((a) => a.type === 'plan') && (
  <button
    onClick={() => togglePlanExpanded(card.id)}
    style={{
      marginTop: '0.5rem',
      padding: '0.2rem 0.6rem',
      fontSize: '0.7rem',
      fontFamily: 'var(--font-mono)',
      background: 'transparent',
      border: '1px solid var(--bg-elevated)',
      borderRadius: '4px',
      color: 'var(--text-muted)',
      cursor: 'pointer',
    }}
  >
    {showPlan ? '▾ Hide Plan' : '▸ Show Plan'}
  </button>
)}
{showPlan && <PlanView cardId={card.id} />}
```

**Note:** The plan toggle appears when the card has a proposed action of type "plan". The PlanView fetches its own data — it won't render anything if no plan exists for the card (returns null on 404).

**Step 2: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add dashboard/frontend/src/features/inbox/CardItem.tsx
git commit -m "Integrate PlanView inline expansion into CardItem"
```

---

### Task 10: Add Plan SSE Events to useSSE Hook

**Files:**
- Modify: `dashboard/frontend/src/hooks/useSSE.ts`

**Step 1: Extend SSE handler for plan events**

Add handling for `plan_step_update` and `plan_complete` event types. The callback already receives arbitrary event data — add new event listeners in the useEffect:

```typescript
es.addEventListener('plan_step_update', (e) => {
  callback({ type: 'plan_step_update', data: JSON.parse(e.data) });
});

es.addEventListener('plan_complete', (e) => {
  callback({ type: 'plan_complete', data: JSON.parse(e.data) });
});
```

**Step 2: Update App.tsx to handle plan SSE events**

In App.tsx, extend the SSE callback to invalidate plan queries:

```typescript
if (event.type === 'plan_step_update' || event.type === 'plan_complete') {
  const cardId = (event.data as { card_id: number }).card_id;
  queryClient.invalidateQueries({ queryKey: ['plan', cardId] });
}
```

**Step 3: Verify no TypeScript errors**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add dashboard/frontend/src/hooks/useSSE.ts dashboard/frontend/src/App.tsx
git commit -m "Add plan_step_update and plan_complete SSE event handling"
```

---

### Task 11: Backend — Emit Plan SSE Events During Execution

**Files:**
- Modify: `dashboard/server.py`

**Step 1: Add SSE emitter for plan step updates**

Find the existing SSE event emitter function (used for cache-invalidate events). Add a helper near the plan endpoints:

```python
def _emit_plan_event(event_type: str, data: dict):
    """Push plan execution events to SSE stream."""
    _sse_queue.put({"event": event_type, "data": json.dumps(data)})
```

**Step 2: Update the execute endpoint to emit events**

In the `/api/cards/{card_id}/plan/execute` handler, after setting `plan.status = "executing"`, add event emission. Since execution happens in Terminal (async), we emit the "dispatched" event immediately. The Terminal session should call back to a webhook to report step completion.

Add a new endpoint for the Terminal session to report back:

```python
@app.post("/api/cards/{card_id}/plan/steps/{step_index}/complete")
async def plan_step_complete(card_id: int, step_index: int, request: Request):
    body = await request.json()
    store = _get_plan_store()
    plan = store.get(card_id)
    if not plan:
        raise HTTPException(404, "No plan")
    step = plan.get_step(step_index)
    if not step:
        raise HTTPException(404, "No step")
    step["status"] = body.get("status", "completed")
    step["output"] = body.get("output", "")
    store.save(plan)
    _emit_plan_event("plan_step_update", {
        "card_id": card_id,
        "step_index": step_index,
        "status": step["status"],
        "output": step["output"],
    })
    # Check if all steps done
    all_steps = [s for phase in plan["phases"] for s in phase["steps"]]
    active = [s for s in all_steps if s["status"] not in ("skipped",)]
    if all(s["status"] in ("completed", "failed") for s in active):
        plan["status"] = "completed"
        plan["executed_at"] = datetime.now(timezone.utc).isoformat()
        store.save(plan)
        succeeded = sum(1 for s in active if s["status"] == "completed")
        failed = sum(1 for s in active if s["status"] == "failed")
        _emit_plan_event("plan_complete", {
            "card_id": card_id,
            "status": "completed",
            "steps_succeeded": succeeded,
            "steps_failed": failed,
        })
    return {"status": "ok"}
```

**Step 3: Verify server starts**

Run: `cd ~/.claude/eng-buddy/dashboard && python -c "import server; print('OK')"`
Expected: OK (or at minimum no SyntaxError)

**Step 4: Commit**

```bash
git add dashboard/server.py
git commit -m "Add plan step completion webhook and SSE event emission"
```

---

### Task 12: Smoke Test — Full Integration

**Step 1: Run TypeScript check**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx tsc --noEmit`
Expected: No errors

**Step 2: Run Vite dev build**

Run: `cd ~/.claude/eng-buddy/dashboard/frontend && npx vite build`
Expected: Build succeeds

**Step 3: Run existing Python tests**

Run: `cd ~/.claude/eng-buddy/dashboard && python -m pytest tests/ -v`
Expected: All existing tests pass

**Step 4: Manual verification**

Open dashboard at localhost:7777, verify:
- Cards still render normally
- Cards with plans show "Show Plan" toggle
- Clicking toggle expands PlanView inline
- Steps display with correct risk badges and status icons
- Approve/Skip/Edit controls appear on high-risk pending steps

**Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "Wave 3: plan approval UX integration complete"
```

---

## Task Dependency Graph

```
Task 1 (types) ─────┐
                     ├─── Task 3 (usePlan hook)
Task 2 (API client) ─┘         │
                                │
Task 4 (Zustand) ──────────────┤
                                │
Task 5 (StepRow) ──────────────┤
                                │
Task 6 (StepEditor) ──────────┤
                                │
Task 7 (PhaseAccordion) ───────┤
                                │
                          Task 8 (PlanView) ──── Task 9 (CardItem integration)
                                                        │
Task 10 (SSE frontend) ────────────────────────────────┤
                                                        │
Task 11 (SSE backend) ─────────────────────────────────┤
                                                        │
                                                  Task 12 (smoke test)
```

Tasks 1+2 can run in parallel. Tasks 4, 5, 6, 7 can run in parallel after 1+2. Task 8 needs all of 3-7. Tasks 9-11 are sequential after 8. Task 12 is final.
