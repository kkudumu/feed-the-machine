# React Dashboard Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the eng-buddy dashboard from vanilla JS to React 18 + TypeScript (Wave 1: Card Inbox core loop)

**Architecture:** Vite + React 18 + TypeScript app in `dashboard/frontend/`. Zustand for UI state, TanStack Query for server state, CSS Modules with custom properties for kawaii theming. Dev server on :5173 proxies API to :7777. Prod builds to `dashboard/static-react/`, FastAPI serves at `/app`.

**Tech Stack:** React 18, TypeScript, Vite, Zustand, @tanstack/react-query, Vitest, React Testing Library, CSS Modules

**Design doc:** `docs/plans/2026-03-10-react-dashboard-design.md`

**Existing prototype reference:** `~/Downloads/eng-buddy-kawaii-dashboard.jsx`

---

### Task 1: Scaffold Vite + React + TypeScript project

**Files:**
- Create: `dashboard/frontend/package.json`
- Create: `dashboard/frontend/tsconfig.json`
- Create: `dashboard/frontend/tsconfig.node.json`
- Create: `dashboard/frontend/vite.config.ts`
- Create: `dashboard/frontend/index.html`
- Create: `dashboard/frontend/src/main.tsx`
- Create: `dashboard/frontend/src/App.tsx`
- Create: `dashboard/frontend/src/vite-env.d.ts`

**Step 1: Create the Vite project**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard
npm create vite@latest frontend -- --template react-ts
```

**Step 2: Install dependencies**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm install zustand @tanstack/react-query
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

**Step 3: Configure Vite proxy**

Replace `dashboard/frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:7777',
      '/ws': {
        target: 'ws://localhost:7777',
        ws: true,
      },
    },
  },
  build: {
    outDir: '../static-react',
    emptyOutDir: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test-setup.ts',
  },
})
```

**Step 4: Create test setup**

Create `dashboard/frontend/src/test-setup.ts`:

```typescript
import '@testing-library/jest-dom'
```

**Step 5: Create minimal App**

Replace `dashboard/frontend/src/App.tsx`:

```tsx
export default function App() {
  return <div>eng-buddy</div>
}
```

Replace `dashboard/frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 3, staleTime: 30_000 },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
```

**Step 6: Verify dev server starts**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run dev
```

Expected: Vite dev server on http://localhost:5173 showing "eng-buddy"

**Step 7: Verify tests run**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run
```

Expected: 0 tests, no errors

**Step 8: Commit**

```bash
git add dashboard/frontend/
git commit -m "Scaffold Vite + React + TypeScript dashboard frontend"
```

---

### Task 2: API types and client

**Files:**
- Create: `dashboard/frontend/src/api/types.ts`
- Create: `dashboard/frontend/src/api/client.ts`
- Create: `dashboard/frontend/src/api/__tests__/client.test.ts`

**Step 1: Write the types**

Create `dashboard/frontend/src/api/types.ts`:

```typescript
export interface Card {
  id: number
  source: string
  classification: string
  status: 'pending' | 'held' | 'approved' | 'completed' | 'failed'
  section: string
  summary: string
  context_notes: string
  timestamp: string
  proposed_actions: Action[]
  draft_response?: string
  analysis_metadata?: Record<string, unknown>
}

export interface Action {
  type: string
  draft: string
  [key: string]: unknown
}

export interface CardCounts {
  pending: number
  held: number
  approved: number
  completed: number
  failed: number
}

export interface CardsResponse {
  cards: Card[]
  counts: CardCounts
}

export interface InboxViewResponse {
  needs_action: Card[]
  no_action: Card[]
}

export interface Poller {
  id: string
  label: string
  next_run_at: string
  last_run_at: string
  health: string
  interval_seconds: number
}

export interface PollersResponse {
  pollers: Poller[]
  generated_at: string
}

export interface StatsResponse {
  pending: number
  held: number
  approved: number
  completed: number
  failed: number
}

export type CardSource = 'all' | 'tasks' | 'freshservice' | 'jira' | 'slack' | 'gmail' | 'calendar'
```

**Step 2: Write the failing test for API client**

Create `dashboard/frontend/src/api/__tests__/client.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchCards, performCardAction, fetchInboxView } from '../client'

const mockFetch = vi.fn()
global.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockReset()
})

describe('fetchCards', () => {
  it('fetches cards with no filter', async () => {
    const mockResponse = { cards: [], counts: { pending: 0, held: 0, approved: 0, completed: 0, failed: 0 } }
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockResponse) })

    const result = await fetchCards()
    expect(mockFetch).toHaveBeenCalledWith('/api/cards?status=all')
    expect(result).toEqual(mockResponse)
  })

  it('fetches cards filtered by source', async () => {
    const mockResponse = { cards: [], counts: { pending: 0, held: 0, approved: 0, completed: 0, failed: 0 } }
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockResponse) })

    const result = await fetchCards('gmail')
    expect(mockFetch).toHaveBeenCalledWith('/api/cards?source=gmail')
    expect(result).toEqual(mockResponse)
  })

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500, statusText: 'Internal Server Error' })

    await expect(fetchCards()).rejects.toThrow('500')
  })
})

describe('performCardAction', () => {
  it('posts action to correct endpoint', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })

    await performCardAction(42, 'send-slack', { message: 'hello' })
    expect(mockFetch).toHaveBeenCalledWith('/api/cards/42/send-slack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'hello' }),
    })
  })
})

describe('fetchInboxView', () => {
  it('fetches inbox view with source and days', async () => {
    const mockResponse = { needs_action: [], no_action: [] }
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockResponse) })

    const result = await fetchInboxView('gmail', 3)
    expect(mockFetch).toHaveBeenCalledWith('/api/inbox-view?source=gmail&days=3')
    expect(result).toEqual(mockResponse)
  })
})
```

**Step 3: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/api/__tests__/client.test.ts
```

Expected: FAIL — module `../client` not found

**Step 4: Write the API client**

Create `dashboard/frontend/src/api/client.ts`:

```typescript
import type { CardsResponse, InboxViewResponse, CardSource } from './types'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export async function fetchCards(source?: CardSource): Promise<CardsResponse> {
  const param = source && source !== 'all' ? `source=${source}` : 'status=all'
  return request<CardsResponse>(`/api/cards?${param}`)
}

export async function fetchInboxView(source: string, days: number = 3): Promise<InboxViewResponse> {
  return request<InboxViewResponse>(`/api/inbox-view?source=${source}&days=${days}`)
}

export async function performCardAction(cardId: number, action: string, body?: Record<string, unknown>): Promise<unknown> {
  return request(`/api/cards/${cardId}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
}

export async function fetchHealth(): Promise<{ status: string }> {
  return request('/api/health')
}
```

**Step 5: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/api/__tests__/client.test.ts
```

Expected: 4 tests PASS

**Step 6: Commit**

```bash
git add dashboard/frontend/src/api/
git commit -m "Add API types and client with tests"
```

---

### Task 3: Kawaii theme and design tokens

**Files:**
- Create: `dashboard/frontend/src/theme/tokens.css`
- Create: `dashboard/frontend/src/theme/global.css`
- Create: `dashboard/frontend/src/theme/glassmorphism.module.css`
- Create: `dashboard/frontend/src/theme/animations.css`

**Step 1: Create design tokens**

Create `dashboard/frontend/src/theme/tokens.css`:

```css
:root {
  /* Backgrounds */
  --bg-deep: #1a1225;
  --bg-surface: #241832;
  --bg-glass: rgba(36, 24, 50, 0.7);
  --bg-glass-hover: rgba(36, 24, 50, 0.85);

  /* Accents */
  --accent-pink: #f4a8c8;
  --accent-mint: #90e3b2;
  --accent-blue: #9ac4ff;
  --accent-coral: #ff9b87;
  --accent-yellow: #f5d97e;

  /* Text */
  --text-primary: #f0e6ff;
  --text-muted: #8b7a9e;

  /* Borders & Glows */
  --radius-card: 16px;
  --radius-button: 10px;
  --radius-badge: 6px;
  --glow-pink: 0 0 20px rgba(244, 168, 200, 0.3);
  --glow-mint: 0 0 20px rgba(144, 227, 178, 0.3);
  --glow-blue: 0 0 20px rgba(154, 196, 255, 0.3);
  --glow-coral: 0 0 20px rgba(255, 155, 135, 0.3);

  /* Source colors */
  --source-gmail: var(--accent-pink);
  --source-slack: var(--accent-mint);
  --source-jira: var(--accent-blue);
  --source-freshservice: var(--accent-coral);
  --source-calendar: var(--accent-yellow);

  /* Typography */
  --font-body: 'Nunito', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

**Step 2: Create global styles**

Create `dashboard/frontend/src/theme/global.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@import './tokens.css';
@import './animations.css';

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-body);
  font-weight: 400;
  background: var(--bg-deep);
  color: var(--text-primary);
  min-height: 100vh;
  overflow-x: hidden;
}

code, pre, kbd {
  font-family: var(--font-mono);
}

::selection {
  background: rgba(244, 168, 200, 0.3);
  color: var(--text-primary);
}

::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: 3px;
}
```

**Step 3: Create animations**

Create `dashboard/frontend/src/theme/animations.css`:

```css
@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); opacity: 0.15; }
  50% { transform: translateY(-20px) rotate(10deg); opacity: 0.25; }
}

@keyframes bounce {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 8px rgba(244, 168, 200, 0.2); }
  50% { box-shadow: 0 0 20px rgba(244, 168, 200, 0.4); }
}

.fade-up {
  animation: fadeUp 0.3s ease-out both;
}

.skeleton {
  background: linear-gradient(90deg, var(--bg-surface) 25%, var(--bg-glass) 50%, var(--bg-surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: var(--radius-card);
}
```

**Step 4: Create glassmorphism module**

Create `dashboard/frontend/src/theme/glassmorphism.module.css`:

```css
.surface {
  background: var(--bg-glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(240, 230, 255, 0.08);
  border-radius: var(--radius-card);
}

.surfaceHover {
  composes: surface;
  transition: background 0.2s, border-color 0.2s, box-shadow 0.2s;
}

.surfaceHover:hover {
  background: var(--bg-glass-hover);
  border-color: rgba(240, 230, 255, 0.15);
}
```

**Step 5: Import global styles in main.tsx**

Update the import in `dashboard/frontend/src/main.tsx` — add at the top:

```typescript
import './theme/global.css'
```

**Step 6: Verify the app renders with the theme**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run dev
```

Expected: Dark purple background (#1a1225), Nunito font loaded

**Step 7: Commit**

```bash
git add dashboard/frontend/src/theme/
git commit -m "Add kawaii design system tokens, global styles, and animations"
```

---

### Task 4: Zustand UI store

**Files:**
- Create: `dashboard/frontend/src/stores/ui.ts`
- Create: `dashboard/frontend/src/stores/__tests__/ui.test.ts`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/stores/__tests__/ui.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '../ui'

beforeEach(() => {
  useUIStore.setState({
    activeSource: 'all',
    activeCardId: null,
    expandedActions: new Set(),
  })
})

describe('useUIStore', () => {
  it('has correct initial state', () => {
    const state = useUIStore.getState()
    expect(state.activeSource).toBe('all')
    expect(state.activeCardId).toBeNull()
    expect(state.expandedActions.size).toBe(0)
  })

  it('sets active source', () => {
    useUIStore.getState().setActiveSource('gmail')
    expect(useUIStore.getState().activeSource).toBe('gmail')
  })

  it('sets active card', () => {
    useUIStore.getState().setActiveCard(42)
    expect(useUIStore.getState().activeCardId).toBe(42)
  })

  it('toggles expanded actions', () => {
    useUIStore.getState().toggleExpandedActions(42)
    expect(useUIStore.getState().expandedActions.has(42)).toBe(true)

    useUIStore.getState().toggleExpandedActions(42)
    expect(useUIStore.getState().expandedActions.has(42)).toBe(false)
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/stores/__tests__/ui.test.ts
```

Expected: FAIL — module `../ui` not found

**Step 3: Write the store**

Create `dashboard/frontend/src/stores/ui.ts`:

```typescript
import { create } from 'zustand'
import type { CardSource } from '../api/types'

interface UIState {
  activeSource: CardSource
  activeCardId: number | null
  expandedActions: Set<number>
  setActiveSource: (source: CardSource) => void
  setActiveCard: (id: number | null) => void
  toggleExpandedActions: (id: number) => void
}

export const useUIStore = create<UIState>((set) => ({
  activeSource: 'all',
  activeCardId: null,
  expandedActions: new Set(),

  setActiveSource: (source) => set({ activeSource: source }),

  setActiveCard: (id) => set({ activeCardId: id }),

  toggleExpandedActions: (id) =>
    set((state) => {
      const next = new Set(state.expandedActions)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { expandedActions: next }
    }),
}))
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/stores/__tests__/ui.test.ts
```

Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/stores/
git commit -m "Add Zustand UI store with source filter and card selection"
```

---

### Task 5: SSE hook for real-time updates

**Files:**
- Create: `dashboard/frontend/src/hooks/useSSE.ts`
- Create: `dashboard/frontend/src/hooks/__tests__/useSSE.test.ts`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/hooks/__tests__/useSSE.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useSSE } from '../useSSE'

let mockEventSource: {
  addEventListener: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
  onopen: (() => void) | null
  onerror: (() => void) | null
}

beforeEach(() => {
  mockEventSource = {
    addEventListener: vi.fn(),
    close: vi.fn(),
    onopen: null,
    onerror: null,
  }
  vi.stubGlobal('EventSource', vi.fn(() => mockEventSource))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useSSE', () => {
  it('creates EventSource connection to /api/events', () => {
    const onEvent = vi.fn()
    renderHook(() => useSSE(onEvent))

    expect(EventSource).toHaveBeenCalledWith('/api/events')
  })

  it('listens for cache-invalidate events', () => {
    const onEvent = vi.fn()
    renderHook(() => useSSE(onEvent))

    expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
      'cache-invalidate',
      expect.any(Function),
    )
  })

  it('listens for message events', () => {
    const onEvent = vi.fn()
    renderHook(() => useSSE(onEvent))

    expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
      'message',
      expect.any(Function),
    )
  })

  it('closes connection on unmount', () => {
    const onEvent = vi.fn()
    const { unmount } = renderHook(() => useSSE(onEvent))

    unmount()
    expect(mockEventSource.close).toHaveBeenCalled()
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/hooks/__tests__/useSSE.test.ts
```

Expected: FAIL — module `../useSSE` not found

**Step 3: Write the SSE hook**

Create `dashboard/frontend/src/hooks/useSSE.ts`:

```typescript
import { useEffect, useRef } from 'react'

export type SSEEvent =
  | { type: 'cache-invalidate'; source: string }
  | { type: 'card'; data: unknown }

export function useSSE(onEvent: (event: SSEEvent) => void) {
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  useEffect(() => {
    const es = new EventSource('/api/events')

    es.addEventListener('cache-invalidate', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        onEventRef.current({ type: 'cache-invalidate', source: data.source })
      } catch { /* ignore malformed */ }
    })

    es.addEventListener('message', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        onEventRef.current({ type: 'card', data })
      } catch { /* ignore malformed */ }
    })

    return () => es.close()
  }, [])
}
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/hooks/__tests__/useSSE.test.ts
```

Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/hooks/
git commit -m "Add SSE hook for real-time card and cache-invalidation events"
```

---

### Task 6: TanStack Query hooks for cards

**Files:**
- Create: `dashboard/frontend/src/hooks/useCards.ts`
- Create: `dashboard/frontend/src/hooks/__tests__/useCards.test.ts`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/hooks/__tests__/useCards.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useCards } from '../useCards'
import * as client from '../../api/client'

vi.mock('../../api/client')

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children)
}

describe('useCards', () => {
  it('fetches cards for the given source', async () => {
    const mockData = {
      cards: [{ id: 1, source: 'gmail', summary: 'test', status: 'pending' }],
      counts: { pending: 1, held: 0, approved: 0, completed: 0, failed: 0 },
    }
    vi.mocked(client.fetchCards).mockResolvedValueOnce(mockData as any)

    const { result } = renderHook(() => useCards('gmail'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockData)
    expect(client.fetchCards).toHaveBeenCalledWith('gmail')
  })

  it('uses "all" as default source', async () => {
    const mockData = { cards: [], counts: { pending: 0, held: 0, approved: 0, completed: 0, failed: 0 } }
    vi.mocked(client.fetchCards).mockResolvedValueOnce(mockData as any)

    const { result } = renderHook(() => useCards('all'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(client.fetchCards).toHaveBeenCalledWith('all')
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/hooks/__tests__/useCards.test.ts
```

Expected: FAIL — module `../useCards` not found

**Step 3: Write the hook**

Create `dashboard/frontend/src/hooks/useCards.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCards, performCardAction } from '../api/client'
import type { CardSource } from '../api/types'

export function useCards(source: CardSource) {
  return useQuery({
    queryKey: ['cards', source],
    queryFn: () => fetchCards(source),
  })
}

export function useCardAction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ cardId, action, body }: { cardId: number; action: string; body?: Record<string, unknown> }) =>
      performCardAction(cardId, action, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards'] })
    },
  })
}
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/hooks/__tests__/useCards.test.ts
```

Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/hooks/useCards.ts dashboard/frontend/src/hooks/__tests__/useCards.test.ts
git commit -m "Add TanStack Query hooks for card fetching and actions"
```

---

### Task 7: Shared UI components — Button, Badge, ChibiMascot

**Files:**
- Create: `dashboard/frontend/src/components/Button.tsx`
- Create: `dashboard/frontend/src/components/Button.module.css`
- Create: `dashboard/frontend/src/components/Badge.tsx`
- Create: `dashboard/frontend/src/components/Badge.module.css`
- Create: `dashboard/frontend/src/components/ChibiMascot.tsx`
- Create: `dashboard/frontend/src/components/__tests__/Button.test.tsx`
- Create: `dashboard/frontend/src/components/__tests__/Badge.test.tsx`
- Create: `dashboard/frontend/src/components/__tests__/ChibiMascot.test.tsx`

**Step 1: Write the failing tests**

Create `dashboard/frontend/src/components/__tests__/Button.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '../Button'

describe('Button', () => {
  it('renders with label', () => {
    render(<Button label="Approve" onClick={() => {}} />)
    expect(screen.getByText('Approve')).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const onClick = vi.fn()
    render(<Button label="Approve" onClick={onClick} />)
    await userEvent.click(screen.getByText('Approve'))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('renders ghost variant', () => {
    render(<Button label="Cancel" variant="ghost" onClick={() => {}} />)
    const btn = screen.getByText('Cancel')
    expect(btn.className).toContain('ghost')
  })

  it('is disabled when disabled prop is true', () => {
    render(<Button label="Send" disabled onClick={() => {}} />)
    expect(screen.getByText('Send')).toBeDisabled()
  })
})
```

Create `dashboard/frontend/src/components/__tests__/Badge.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from '../Badge'

describe('Badge', () => {
  it('renders text', () => {
    render(<Badge text="API" />)
    expect(screen.getByText('API')).toBeInTheDocument()
  })

  it('applies color variant', () => {
    render(<Badge text="MCP" color="mint" />)
    const badge = screen.getByText('MCP')
    expect(badge.className).toContain('mint')
  })
})
```

Create `dashboard/frontend/src/components/__tests__/ChibiMascot.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChibiMascot } from '../ChibiMascot'

describe('ChibiMascot', () => {
  it('renders with happy mood', () => {
    render(<ChibiMascot mood="happy" />)
    expect(screen.getByLabelText('mascot-happy')).toBeInTheDocument()
  })

  it('renders with thinking mood', () => {
    render(<ChibiMascot mood="thinking" />)
    expect(screen.getByLabelText('mascot-thinking')).toBeInTheDocument()
  })

  it('renders with sleepy mood', () => {
    render(<ChibiMascot mood="sleepy" />)
    expect(screen.getByLabelText('mascot-sleepy')).toBeInTheDocument()
  })

  it('renders with excited mood', () => {
    render(<ChibiMascot mood="excited" />)
    expect(screen.getByLabelText('mascot-excited')).toBeInTheDocument()
  })
})
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/components/__tests__/
```

Expected: FAIL — modules not found

**Step 3: Write Button component**

Create `dashboard/frontend/src/components/Button.module.css`:

```css
.button {
  font-family: var(--font-body);
  font-weight: 600;
  font-size: 0.85rem;
  padding: 8px 16px;
  border-radius: var(--radius-button);
  border: none;
  cursor: pointer;
  transition: transform 0.1s, background 0.2s, box-shadow 0.2s;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.button:active:not(:disabled) {
  transform: scale(0.96);
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.primary {
  background: var(--accent-pink);
  color: var(--bg-deep);
}

.primary:hover:not(:disabled) {
  box-shadow: var(--glow-pink);
}

.ghost {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid rgba(240, 230, 255, 0.15);
}

.ghost:hover:not(:disabled) {
  background: rgba(240, 230, 255, 0.05);
  border-color: rgba(240, 230, 255, 0.25);
}

.mint {
  background: var(--accent-mint);
  color: var(--bg-deep);
}

.coral {
  background: var(--accent-coral);
  color: var(--bg-deep);
}
```

Create `dashboard/frontend/src/components/Button.tsx`:

```tsx
import styles from './Button.module.css'

interface ButtonProps {
  label: string
  onClick: () => void
  variant?: 'primary' | 'ghost' | 'mint' | 'coral'
  disabled?: boolean
}

export function Button({ label, onClick, variant = 'primary', disabled = false }: ButtonProps) {
  return (
    <button
      className={`${styles.button} ${styles[variant]}`}
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </button>
  )
}
```

**Step 4: Write Badge component**

Create `dashboard/frontend/src/components/Badge.module.css`:

```css
.badge {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-badge);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pink {
  background: rgba(244, 168, 200, 0.15);
  color: var(--accent-pink);
  border: 1px solid rgba(244, 168, 200, 0.3);
}

.mint {
  background: rgba(144, 227, 178, 0.15);
  color: var(--accent-mint);
  border: 1px solid rgba(144, 227, 178, 0.3);
}

.blue {
  background: rgba(154, 196, 255, 0.15);
  color: var(--accent-blue);
  border: 1px solid rgba(154, 196, 255, 0.3);
}

.coral {
  background: rgba(255, 155, 135, 0.15);
  color: var(--accent-coral);
  border: 1px solid rgba(255, 155, 135, 0.3);
}

.muted {
  background: rgba(139, 122, 158, 0.15);
  color: var(--text-muted);
  border: 1px solid rgba(139, 122, 158, 0.3);
}
```

Create `dashboard/frontend/src/components/Badge.tsx`:

```tsx
import styles from './Badge.module.css'

interface BadgeProps {
  text: string
  color?: 'pink' | 'mint' | 'blue' | 'coral' | 'muted'
}

export function Badge({ text, color = 'muted' }: BadgeProps) {
  return <span className={`${styles.badge} ${styles[color]}`}>{text}</span>
}
```

**Step 5: Write ChibiMascot component**

Create `dashboard/frontend/src/components/ChibiMascot.tsx`:

```tsx
export type MascotMood = 'happy' | 'thinking' | 'sleepy' | 'excited'

interface ChibiMascotProps {
  mood: MascotMood
  size?: number
}

const faces: Record<MascotMood, { eyes: string; mouth: string; extras?: string }> = {
  happy: { eyes: '●  ●', mouth: 'ω', extras: '' },
  thinking: { eyes: '●  ◐', mouth: 'ω', extras: '?' },
  sleepy: { eyes: '−  −', mouth: 'ω', extras: 'z' },
  excited: { eyes: '✧  ✧', mouth: 'ω', extras: '!' },
}

export function ChibiMascot({ mood, size = 48 }: ChibiMascotProps) {
  const face = faces[mood]

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      aria-label={`mascot-${mood}`}
      style={mood === 'excited' ? { animation: 'bounce 0.6s ease-in-out infinite' } : undefined}
    >
      {/* Ears */}
      <polygon points="12,22 8,4 24,16" fill="#f4a8c8" opacity="0.8" />
      <polygon points="52,22 56,4 40,16" fill="#f4a8c8" opacity="0.8" />
      {/* Inner ears */}
      <polygon points="14,20 11,8 22,16" fill="#ff9b87" opacity="0.5" />
      <polygon points="50,20 53,8 42,16" fill="#ff9b87" opacity="0.5" />
      {/* Head */}
      <ellipse cx="32" cy="36" rx="22" ry="20" fill="#241832" stroke="#f4a8c8" strokeWidth="1.5" />
      {/* Eyes */}
      <text x="32" y="34" textAnchor="middle" fill="#f0e6ff" fontSize="8" fontFamily="monospace">
        {face.eyes}
      </text>
      {/* Mouth */}
      <text x="32" y="44" textAnchor="middle" fill="#f4a8c8" fontSize="10" fontFamily="monospace">
        {face.mouth}
      </text>
      {/* Extras */}
      {face.extras && (
        <text x="54" y="16" fill="#9ac4ff" fontSize="10" fontFamily="monospace" opacity="0.7">
          {face.extras}
        </text>
      )}
    </svg>
  )
}
```

**Step 6: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/components/__tests__/
```

Expected: 10 tests PASS

**Step 7: Commit**

```bash
git add dashboard/frontend/src/components/
git commit -m "Add Button, Badge, and ChibiMascot shared components with tests"
```

---

### Task 8: Sidebar component with source filters

**Files:**
- Create: `dashboard/frontend/src/features/inbox/Sidebar.tsx`
- Create: `dashboard/frontend/src/features/inbox/Sidebar.module.css`
- Create: `dashboard/frontend/src/features/inbox/__tests__/Sidebar.test.tsx`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/features/inbox/__tests__/Sidebar.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Sidebar } from '../Sidebar'
import { useUIStore } from '../../../stores/ui'

beforeEach(() => {
  useUIStore.setState({ activeSource: 'all' })
})

const mockCounts = { pending: 5, held: 2, approved: 3, completed: 10, failed: 1 }
const mockSourceCounts: Record<string, number> = {
  gmail: 3,
  slack: 2,
  jira: 4,
  freshservice: 1,
  calendar: 2,
}

describe('Sidebar', () => {
  it('renders all source filters', () => {
    render(<Sidebar counts={mockCounts} sourceCounts={mockSourceCounts} />)
    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText('Gmail')).toBeInTheDocument()
    expect(screen.getByText('Slack')).toBeInTheDocument()
    expect(screen.getByText('Jira')).toBeInTheDocument()
  })

  it('shows count badges', () => {
    render(<Sidebar counts={mockCounts} sourceCounts={mockSourceCounts} />)
    expect(screen.getByText('3')).toBeInTheDocument() // gmail
  })

  it('highlights active source', () => {
    useUIStore.setState({ activeSource: 'gmail' })
    render(<Sidebar counts={mockCounts} sourceCounts={mockSourceCounts} />)
    const gmailItem = screen.getByText('Gmail').closest('button')
    expect(gmailItem?.className).toContain('active')
  })

  it('changes active source on click', async () => {
    render(<Sidebar counts={mockCounts} sourceCounts={mockSourceCounts} />)
    await userEvent.click(screen.getByText('Slack'))
    expect(useUIStore.getState().activeSource).toBe('slack')
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/features/inbox/__tests__/Sidebar.test.tsx
```

Expected: FAIL — module `../Sidebar` not found

**Step 3: Write Sidebar component**

Create `dashboard/frontend/src/features/inbox/Sidebar.module.css`:

```css
.sidebar {
  width: 220px;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-body);
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  border-left: 3px solid transparent;
  border-radius: 0 8px 8px 0;
  transition: all 0.15s;
  width: 100%;
  text-align: left;
}

.item:hover {
  background: rgba(240, 230, 255, 0.04);
  color: var(--text-primary);
}

.active {
  border-left-color: var(--accent-pink);
  color: var(--text-primary);
  background: rgba(244, 168, 200, 0.06);
}

.count {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background: rgba(240, 230, 255, 0.08);
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 24px;
  text-align: center;
}

.divider {
  height: 1px;
  background: rgba(240, 230, 255, 0.06);
  margin: 8px 16px;
}
```

Create `dashboard/frontend/src/features/inbox/Sidebar.tsx`:

```tsx
import { useUIStore } from '../../stores/ui'
import type { CardCounts, CardSource } from '../../api/types'
import styles from './Sidebar.module.css'

interface SidebarProps {
  counts: CardCounts
  sourceCounts: Record<string, number>
}

const sources: { key: CardSource; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'gmail', label: 'Gmail' },
  { key: 'slack', label: 'Slack' },
  { key: 'jira', label: 'Jira' },
  { key: 'freshservice', label: 'Freshservice' },
  { key: 'calendar', label: 'Calendar' },
  { key: 'tasks', label: 'Tasks' },
]

export function Sidebar({ counts, sourceCounts }: SidebarProps) {
  const activeSource = useUIStore((s) => s.activeSource)
  const setActiveSource = useUIStore((s) => s.setActiveSource)

  const getCount = (key: CardSource): number => {
    if (key === 'all') return counts.pending
    return sourceCounts[key] ?? 0
  }

  return (
    <nav className={styles.sidebar}>
      {sources.map(({ key, label }) => (
        <button
          key={key}
          className={`${styles.item} ${activeSource === key ? styles.active : ''}`}
          onClick={() => setActiveSource(key)}
        >
          <span>{label}</span>
          {getCount(key) > 0 && <span className={styles.count}>{getCount(key)}</span>}
        </button>
      ))}
    </nav>
  )
}
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/features/inbox/__tests__/Sidebar.test.tsx
```

Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/features/inbox/
git commit -m "Add Sidebar component with source filters and active state"
```

---

### Task 9: Stats bar component

**Files:**
- Create: `dashboard/frontend/src/features/stats/StatsBar.tsx`
- Create: `dashboard/frontend/src/features/stats/StatsBar.module.css`
- Create: `dashboard/frontend/src/features/stats/__tests__/StatsBar.test.tsx`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/features/stats/__tests__/StatsBar.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatsBar } from '../StatsBar'

describe('StatsBar', () => {
  it('renders all stat values', () => {
    render(
      <StatsBar
        needsAction={12}
        autoResolved={34}
        draftAcceptRate={87}
        timeSavedMinutes={120}
      />,
    )
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('34')).toBeInTheDocument()
    expect(screen.getByText('87%')).toBeInTheDocument()
    expect(screen.getByText('2h 0m')).toBeInTheDocument()
  })

  it('renders stat labels', () => {
    render(
      <StatsBar needsAction={0} autoResolved={0} draftAcceptRate={0} timeSavedMinutes={0} />,
    )
    expect(screen.getByText('Needs Action')).toBeInTheDocument()
    expect(screen.getByText('Auto-Resolved')).toBeInTheDocument()
    expect(screen.getByText('Draft Accept Rate')).toBeInTheDocument()
    expect(screen.getByText('Time Saved')).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/features/stats/__tests__/StatsBar.test.tsx
```

Expected: FAIL — module `../StatsBar` not found

**Step 3: Write StatsBar component**

Create `dashboard/frontend/src/features/stats/StatsBar.module.css`:

```css
.bar {
  display: flex;
  gap: 16px;
  padding: 16px 24px;
}

.stat {
  flex: 1;
  background: var(--bg-glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(240, 230, 255, 0.08);
  border-radius: var(--radius-card);
  padding: 16px 20px;
  text-align: center;
}

.value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 6px;
}
```

Create `dashboard/frontend/src/features/stats/StatsBar.tsx`:

```tsx
import styles from './StatsBar.module.css'

interface StatsBarProps {
  needsAction: number
  autoResolved: number
  draftAcceptRate: number
  timeSavedMinutes: number
}

function formatTime(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${h}h ${m}m`
}

export function StatsBar({ needsAction, autoResolved, draftAcceptRate, timeSavedMinutes }: StatsBarProps) {
  return (
    <div className={styles.bar}>
      <div className={styles.stat}>
        <div className={styles.value}>{needsAction}</div>
        <div className={styles.label}>Needs Action</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.value}>{autoResolved}</div>
        <div className={styles.label}>Auto-Resolved</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.value}>{draftAcceptRate}%</div>
        <div className={styles.label}>Draft Accept Rate</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.value}>{formatTime(timeSavedMinutes)}</div>
        <div className={styles.label}>Time Saved</div>
      </div>
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/features/stats/__tests__/StatsBar.test.tsx
```

Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/features/stats/
git commit -m "Add StatsBar component with hero metrics display"
```

---

### Task 10: Card component with source-coded glow borders

**Files:**
- Create: `dashboard/frontend/src/features/inbox/CardItem.tsx`
- Create: `dashboard/frontend/src/features/inbox/CardItem.module.css`
- Create: `dashboard/frontend/src/features/inbox/__tests__/CardItem.test.tsx`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/features/inbox/__tests__/CardItem.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CardItem } from '../CardItem'
import type { Card } from '../../../api/types'

const mockCard: Card = {
  id: 1,
  source: 'gmail',
  classification: 'high',
  status: 'pending',
  section: 'needs_action',
  summary: 'RE: Q3 Budget Review - needs approval by Friday',
  context_notes: 'From: cfo@company.com',
  timestamp: '2026-03-10T09:00:00Z',
  proposed_actions: [
    { type: 'send-email', draft: 'Thanks for sharing. I will review and approve by EOD Thursday.' },
  ],
  draft_response: 'Thanks for sharing. I will review and approve by EOD Thursday.',
}

describe('CardItem', () => {
  it('renders card summary', () => {
    render(<CardItem card={mockCard} />)
    expect(screen.getByText(/Q3 Budget Review/)).toBeInTheDocument()
  })

  it('renders source badge', () => {
    render(<CardItem card={mockCard} />)
    expect(screen.getByText('gmail')).toBeInTheDocument()
  })

  it('renders timestamp', () => {
    render(<CardItem card={mockCard} />)
    expect(screen.getByText(/9:00/)).toBeInTheDocument()
  })

  it('shows draft when present', () => {
    render(<CardItem card={mockCard} />)
    expect(screen.getByText(/I will review and approve/)).toBeInTheDocument()
  })

  it('applies source-specific glow class', () => {
    const { container } = render(<CardItem card={mockCard} />)
    const cardEl = container.firstChild as HTMLElement
    expect(cardEl.className).toContain('gmail')
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/features/inbox/__tests__/CardItem.test.tsx
```

Expected: FAIL — module `../CardItem` not found

**Step 3: Write CardItem component**

Create `dashboard/frontend/src/features/inbox/CardItem.module.css`:

```css
.card {
  background: var(--bg-glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(240, 230, 255, 0.08);
  border-radius: var(--radius-card);
  padding: 16px 20px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.card:hover {
  background: var(--bg-glass-hover);
}

.gmail { border-color: rgba(244, 168, 200, 0.25); }
.gmail:hover { box-shadow: var(--glow-pink); }

.slack { border-color: rgba(144, 227, 178, 0.25); }
.slack:hover { box-shadow: var(--glow-mint); }

.jira { border-color: rgba(154, 196, 255, 0.25); }
.jira:hover { box-shadow: var(--glow-blue); }

.freshservice { border-color: rgba(255, 155, 135, 0.25); }
.freshservice:hover { box-shadow: var(--glow-coral); }

.calendar { border-color: rgba(245, 217, 126, 0.25); }

.header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.summary {
  font-weight: 600;
  font-size: 0.95rem;
  flex: 1;
}

.meta {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.draft {
  margin-top: 10px;
  padding: 10px 14px;
  background: rgba(144, 227, 178, 0.06);
  border: 1px solid rgba(144, 227, 178, 0.2);
  border-radius: 10px;
  font-size: 0.85rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
```

Create `dashboard/frontend/src/features/inbox/CardItem.tsx`:

```tsx
import type { Card } from '../../api/types'
import { Badge } from '../../components/Badge'
import styles from './CardItem.module.css'

interface CardItemProps {
  card: Card
  style?: React.CSSProperties
}

const sourceColors: Record<string, 'pink' | 'mint' | 'blue' | 'coral' | 'muted'> = {
  gmail: 'pink',
  slack: 'mint',
  jira: 'blue',
  freshservice: 'coral',
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

export function CardItem({ card, style }: CardItemProps) {
  const sourceClass = styles[card.source] ?? ''

  return (
    <div className={`${styles.card} ${sourceClass}`} style={style}>
      <div className={styles.header}>
        <Badge text={card.source} color={sourceColors[card.source] ?? 'muted'} />
        <span className={styles.summary}>{card.summary}</span>
        <span className={styles.meta}>{formatTime(card.timestamp)}</span>
      </div>
      {card.context_notes && (
        <div className={styles.meta}>{card.context_notes}</div>
      )}
      {card.draft_response && (
        <div className={styles.draft}>{card.draft_response}</div>
      )}
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/features/inbox/__tests__/CardItem.test.tsx
```

Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/features/inbox/CardItem.tsx dashboard/frontend/src/features/inbox/CardItem.module.css dashboard/frontend/src/features/inbox/__tests__/CardItem.test.tsx
git commit -m "Add CardItem component with source-coded glow borders and draft display"
```

---

### Task 11: Card list with stagger animation and SSE integration

**Files:**
- Create: `dashboard/frontend/src/features/inbox/CardList.tsx`
- Create: `dashboard/frontend/src/features/inbox/CardList.module.css`
- Create: `dashboard/frontend/src/features/inbox/__tests__/CardList.test.tsx`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/features/inbox/__tests__/CardList.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { CardList } from '../CardList'
import * as client from '../../../api/client'
import { useUIStore } from '../../../stores/ui'

vi.mock('../../../api/client')

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children)
}

describe('CardList', () => {
  it('renders cards from API', async () => {
    useUIStore.setState({ activeSource: 'all' })
    vi.mocked(client.fetchCards).mockResolvedValueOnce({
      cards: [
        { id: 1, source: 'gmail', summary: 'Budget review', status: 'pending', classification: 'high', section: '', context_notes: '', timestamp: '2026-03-10T09:00:00Z', proposed_actions: [] },
        { id: 2, source: 'slack', summary: 'Deploy question', status: 'pending', classification: 'low', section: '', context_notes: '', timestamp: '2026-03-10T10:00:00Z', proposed_actions: [] },
      ],
      counts: { pending: 2, held: 0, approved: 0, completed: 0, failed: 0 },
    } as any)

    render(createElement(createWrapper(), null, createElement(CardList)))

    expect(await screen.findByText(/Budget review/)).toBeInTheDocument()
    expect(await screen.findByText(/Deploy question/)).toBeInTheDocument()
  })

  it('shows loading skeleton when fetching', () => {
    useUIStore.setState({ activeSource: 'all' })
    vi.mocked(client.fetchCards).mockReturnValueOnce(new Promise(() => {}))

    render(createElement(createWrapper(), null, createElement(CardList)))

    expect(screen.getByTestId('card-list-loading')).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/features/inbox/__tests__/CardList.test.tsx
```

Expected: FAIL — module `../CardList` not found

**Step 3: Write CardList component**

Create `dashboard/frontend/src/features/inbox/CardList.module.css`:

```css
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 24px 24px;
  flex: 1;
}

.skeletonCard {
  height: 100px;
  border-radius: var(--radius-card);
}

.empty {
  text-align: center;
  padding: 48px 24px;
  color: var(--text-muted);
  font-size: 0.95rem;
}
```

Create `dashboard/frontend/src/features/inbox/CardList.tsx`:

```tsx
import { useCards } from '../../hooks/useCards'
import { useUIStore } from '../../stores/ui'
import { CardItem } from './CardItem'
import styles from './CardList.module.css'

export function CardList() {
  const activeSource = useUIStore((s) => s.activeSource)
  const { data, isLoading } = useCards(activeSource)

  if (isLoading) {
    return (
      <div className={styles.list} data-testid="card-list-loading">
        {[1, 2, 3].map((i) => (
          <div key={i} className={`skeleton ${styles.skeletonCard}`} />
        ))}
      </div>
    )
  }

  const cards = data?.cards ?? []

  if (cards.length === 0) {
    return <div className={styles.empty}>No cards right now. All clear!</div>
  }

  return (
    <div className={styles.list}>
      {cards.map((card, index) => (
        <CardItem
          key={card.id}
          card={card}
          style={{
            animation: `fadeUp 0.3s ease-out both`,
            animationDelay: `${index * 50}ms`,
          }}
        />
      ))}
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/features/inbox/__tests__/CardList.test.tsx
```

Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/features/inbox/CardList.tsx dashboard/frontend/src/features/inbox/CardList.module.css dashboard/frontend/src/features/inbox/__tests__/CardList.test.tsx
git commit -m "Add CardList with stagger animation and loading skeleton"
```

---

### Task 12: App shell — wire everything together

**Files:**
- Modify: `dashboard/frontend/src/App.tsx`
- Create: `dashboard/frontend/src/App.module.css`
- Create: `dashboard/frontend/src/features/inbox/Header.tsx`
- Create: `dashboard/frontend/src/features/inbox/Header.module.css`
- Create: `dashboard/frontend/src/__tests__/App.test.tsx`

**Step 1: Write the failing test**

Create `dashboard/frontend/src/__tests__/App.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import App from '../App'
import * as client from '../api/client'

vi.mock('../api/client')
vi.stubGlobal('EventSource', vi.fn(() => ({
  addEventListener: vi.fn(),
  close: vi.fn(),
  onopen: null,
  onerror: null,
})))

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children)
}

describe('App', () => {
  it('renders header with eng-buddy title', async () => {
    vi.mocked(client.fetchCards).mockResolvedValueOnce({
      cards: [],
      counts: { pending: 0, held: 0, approved: 0, completed: 0, failed: 0 },
    } as any)

    render(createElement(createWrapper(), null, createElement(App)))

    expect(screen.getByText('ENG-BUDDY')).toBeInTheDocument()
  })

  it('renders sidebar', async () => {
    vi.mocked(client.fetchCards).mockResolvedValueOnce({
      cards: [],
      counts: { pending: 0, held: 0, approved: 0, completed: 0, failed: 0 },
    } as any)

    render(createElement(createWrapper(), null, createElement(App)))

    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText('Gmail')).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/__tests__/App.test.tsx
```

Expected: FAIL — missing components

**Step 3: Write Header component**

Create `dashboard/frontend/src/features/inbox/Header.module.css`:

```css
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(240, 230, 255, 0.06);
}

.titleGroup {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-weight: 700;
  font-size: 1.3rem;
  letter-spacing: 2px;
  background: linear-gradient(135deg, var(--accent-pink), var(--accent-blue));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

Create `dashboard/frontend/src/features/inbox/Header.tsx`:

```tsx
import { ChibiMascot } from '../../components/ChibiMascot'
import type { MascotMood } from '../../components/ChibiMascot'
import styles from './Header.module.css'

interface HeaderProps {
  pendingCount: number
  isLoading: boolean
}

function getMood(pendingCount: number, isLoading: boolean): MascotMood {
  if (isLoading) return 'thinking'
  if (pendingCount === 0) return 'happy'
  if (pendingCount > 10) return 'sleepy'
  return 'happy'
}

export function Header({ pendingCount, isLoading }: HeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.titleGroup}>
        <ChibiMascot mood={getMood(pendingCount, isLoading)} size={40} />
        <span className={styles.title}>ENG-BUDDY</span>
      </div>
    </header>
  )
}
```

**Step 4: Write App shell**

Create `dashboard/frontend/src/App.module.css`:

```css
.layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.body {
  display: flex;
  flex: 1;
}

.content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.particles {
  position: fixed;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}

.particle {
  position: absolute;
  animation: float 8s ease-in-out infinite;
  opacity: 0.15;
  font-size: 14px;
  color: var(--accent-pink);
}
```

Update `dashboard/frontend/src/App.tsx`:

```tsx
import { useCallback, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useSSE } from './hooks/useSSE'
import type { SSEEvent } from './hooks/useSSE'
import { useCards } from './hooks/useCards'
import { useUIStore } from './stores/ui'
import { Header } from './features/inbox/Header'
import { Sidebar } from './features/inbox/Sidebar'
import { CardList } from './features/inbox/CardList'
import { StatsBar } from './features/stats/StatsBar'
import styles from './App.module.css'

const particles = ['✿', '⋆', '♡', '✧', '✿', '⋆', '♡', '✧']

export default function App() {
  const queryClient = useQueryClient()
  const activeSource = useUIStore((s) => s.activeSource)
  const { data, isLoading } = useCards(activeSource)

  const handleSSE = useCallback(
    (event: SSEEvent) => {
      if (event.type === 'cache-invalidate') {
        queryClient.invalidateQueries({ queryKey: ['cards'] })
      } else {
        queryClient.invalidateQueries({ queryKey: ['cards'] })
      }
    },
    [queryClient],
  )

  useSSE(handleSSE)

  const counts = data?.counts ?? { pending: 0, held: 0, approved: 0, completed: 0, failed: 0 }

  const sourceCounts = useMemo(() => {
    const cards = data?.cards ?? []
    const result: Record<string, number> = {}
    for (const card of cards) {
      result[card.source] = (result[card.source] ?? 0) + 1
    }
    return result
  }, [data?.cards])

  return (
    <div className={styles.layout}>
      {/* Background particles */}
      <div className={styles.particles}>
        {particles.map((p, i) => (
          <span
            key={i}
            className={styles.particle}
            style={{
              left: `${10 + i * 12}%`,
              top: `${20 + (i % 3) * 25}%`,
              animationDelay: `${i * 1.2}s`,
              animationDuration: `${6 + (i % 4) * 2}s`,
            }}
          >
            {p}
          </span>
        ))}
      </div>

      <Header pendingCount={counts.pending} isLoading={isLoading} />

      <StatsBar
        needsAction={counts.pending}
        autoResolved={counts.completed}
        draftAcceptRate={counts.completed > 0 ? Math.round((counts.approved / (counts.approved + counts.failed || 1)) * 100) : 0}
        timeSavedMinutes={counts.completed * 5}
      />

      <div className={styles.body}>
        <Sidebar counts={counts} sourceCounts={sourceCounts} />
        <div className={styles.content}>
          <CardList />
        </div>
      </div>
    </div>
  )
}
```

**Step 5: Run tests to verify they pass**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run
```

Expected: All tests PASS

**Step 6: Verify visually**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run dev
```

Expected: Dark kawaii dashboard with header (mascot + title), stats bar, sidebar with source filters, and card list (showing skeleton loading if backend not running, cards if it is)

**Step 7: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Wire App shell with Header, Sidebar, StatsBar, CardList, and SSE integration"
```

---

### Task 13: FastAPI integration — serve React at /app

**Files:**
- Modify: `dashboard/server.py:~line 1-30` (imports and mount)

**Step 1: Read current server.py mount configuration**

```bash
head -40 /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/server.py
```

Understand where StaticFiles is mounted and the root route.

**Step 2: Build the React app**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run build
```

Expected: Build output in `dashboard/static-react/`

**Step 3: Add React mount to server.py**

Add after the existing StaticFiles mount:

```python
# React dashboard (new)
react_dir = Path(__file__).parent / "static-react"
if react_dir.exists():
    app.mount("/app-assets", StaticFiles(directory=str(react_dir / "assets")), name="react-assets")

    @app.get("/app")
    @app.get("/app/{path:path}")
    async def serve_react(path: str = ""):
        return FileResponse(str(react_dir / "index.html"))
```

**Step 4: Update Vite config base path**

In `dashboard/frontend/vite.config.ts`, add base:

```typescript
export default defineConfig({
  base: '/app-assets/../app/',
  // ... rest of config
})
```

Actually, simpler approach — update `vite.config.ts`:

```typescript
build: {
  outDir: '../static-react',
  emptyOutDir: true,
},
```

And in the React `index.html`, asset paths will be relative. The FastAPI catch-all at `/app` serves `index.html`, and Vite's default asset paths will work with the `/app-assets` mount.

**Step 5: Rebuild and verify**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run build
```

Then start the FastAPI server and visit `http://localhost:7777/app` — should show the React dashboard.

**Step 6: Verify vanilla JS still works**

Visit `http://localhost:7777/` — should still show the original dashboard.

**Step 7: Commit**

```bash
git add dashboard/server.py dashboard/frontend/ dashboard/static-react/
git commit -m "Serve React dashboard at /app alongside vanilla JS at /"
```

---

### Task 14: Add .gitignore entries for frontend

**Files:**
- Modify: `.gitignore`

**Step 1: Add frontend entries**

Add to `.gitignore`:

```
dashboard/frontend/node_modules/
dashboard/frontend/dist/
dashboard/static-react/
```

Note: We do NOT gitignore `dashboard/static-react/` if we want prod builds committed. Decision: keep it ignored and build on deploy, or commit it for simplicity. For a single-user tool, committing the build is fine — remove the `dashboard/static-react/` line if you prefer that.

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "Add frontend build artifacts to .gitignore"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Vite + React + TS scaffold | 0 (setup) |
| 2 | API types and client | 4 |
| 3 | Kawaii design tokens | 0 (CSS) |
| 4 | Zustand UI store | 4 |
| 5 | SSE hook | 4 |
| 6 | TanStack Query card hooks | 2 |
| 7 | Button, Badge, ChibiMascot | 10 |
| 8 | Sidebar with source filters | 4 |
| 9 | StatsBar hero metrics | 2 |
| 10 | CardItem with source glows | 5 |
| 11 | CardList with stagger animation | 2 |
| 12 | App shell — wire everything | 2 |
| 13 | FastAPI serve React at /app | 0 (integration) |
| 14 | .gitignore updates | 0 (config) |

**Total: 14 tasks, ~39 tests, covers full Wave 1 (Card Inbox)**

After Wave 1 is complete, Wave 2 (Execution & Feedback) builds on this foundation with WebSocket terminal, action dispatch wiring, toast notifications, and card status transitions.
