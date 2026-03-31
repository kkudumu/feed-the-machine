# React Dashboard Wave 2 Implementation Plan — Full Vanilla JS Parity

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Port every remaining vanilla JS feature to React, making the React app the sole dashboard. Retire `static/app.js`.

**Architecture:** Extend the existing React 18 + TypeScript + Vite app in `dashboard/frontend/`. Add React Router v6 for tab navigation, xterm.js for WebSocket terminal, 6 CSS variable theme sets. All server data via TanStack Query. Zustand for UI/toast/debug state.

**Tech Stack:** React 18, TypeScript, Vite, Zustand, @tanstack/react-query, React Router v6, xterm.js, CSS Modules

**Design doc:** `docs/plans/2026-03-10-react-dashboard-wave2-design.md`

**Dependency map:**
- Tasks 1-4: independent (parallel)
- Task 5: depends on 1
- Tasks 6-8: depend on 2, 3, 4, 5
- Tasks 9-11: depend on 4, 5
- Tasks 12-14: depend on 3, 4
- Tasks 15-20: depend on 4, 5
- Task 21: depends on 4, 5
- Task 22: depends on all

---

### Task 1: Install new dependencies

**Files:**
- Modify: `dashboard/frontend/package.json`

**Step 1: Install production dependencies**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm install react-router-dom@^7 xterm @xterm/addon-fit
```

**Step 2: Verify installation**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
node -e "require('react-router-dom'); require('xterm'); require('@xterm/addon-fit'); console.log('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add dashboard/frontend/package.json dashboard/frontend/package-lock.json
git commit -m "Install react-router-dom, xterm, and xterm fit addon for Wave 2"
```

---

### Task 2: Theme CSS system — 6 variable sets

**Files:**
- Create: `dashboard/frontend/src/theme/themes.css`
- Modify: `dashboard/frontend/src/theme/tokens.css`
- Modify: `dashboard/frontend/src/theme/global.css`

**Step 1: Create `themes.css` with all 6 theme variable sets**

The vanilla JS dashboard has 6 CSS files in `dashboard/static/themes/`. Each defines ~30 CSS variables. Convert these into attribute-selector blocks.

Create `dashboard/frontend/src/theme/themes.css`:

```css
/* ===== NEON DREAMS (default) ===== */

[data-theme="neon-dreams"][data-mode="dark"] {
  --bg: #0d0221;
  --card-bg: #150535;
  --surface: #120430;
  --surface-alt: #1a0840;
  --border: #ff71ce;
  --border-subtle: #44206b;
  --border-faint: #26104d;
  --text: #f1e8ff;
  --muted: #9d8bbb;
  --hover-bg: rgba(255, 113, 206, 0.12);
  --overlay-bg: rgba(13, 2, 33, 0.92);
  --shadow: 0 0 14px rgba(255, 113, 206, 0.32), 0 0 34px rgba(1, 205, 254, 0.1);
  --shadow-sm: 0 0 10px rgba(255, 113, 206, 0.24);
  --shadow-hover: 0 0 20px rgba(255, 113, 206, 0.45), 0 0 44px rgba(1, 205, 254, 0.16);
  --font: 'JetBrains Mono', monospace;
  --font-heading: 'VT323', monospace;
  --radius: 0;
  --radius-sm: 0;
  --transition-speed: 0.15s;
  --fresh: #05ffa1;
  --jira: #01cdfe;
  --slack: #ff71ce;
  --gmail: #ff6b6b;
  --urgent: #ffffff;
  --needs-response: #fffb96;
  --debug-info: #01cdfe;
  --debug-error: #ff6b6b;
  --debug-surface: rgba(13, 2, 33, 0.97);
  --error-row-bg: rgba(255, 107, 107, 0.12);
  --held-stripe: repeating-linear-gradient(45deg, #24114b, #24114b 4px, #150535 4px, #150535 8px);
}

[data-theme="neon-dreams"][data-mode="light"] {
  --bg: #e8d5f5;
  --card-bg: rgba(255, 255, 255, 0.72);
  --surface: rgba(255, 255, 255, 0.62);
  --surface-alt: rgba(255, 255, 255, 0.52);
  --border: #ec6dcb;
  --border-subtle: #caa6dc;
  --border-faint: #d7b7e6;
  --text: #33114e;
  --muted: #815f9f;
  --hover-bg: rgba(236, 109, 203, 0.12);
  --overlay-bg: rgba(232, 213, 245, 0.88);
  --shadow: 0 8px 24px rgba(129, 95, 159, 0.18);
  --shadow-sm: 0 6px 16px rgba(129, 95, 159, 0.14);
  --shadow-hover: 0 12px 32px rgba(79, 143, 230, 0.2);
  --font: 'JetBrains Mono', monospace;
  --font-heading: 'VT323', monospace;
  --radius: 0;
  --radius-sm: 0;
  --transition-speed: 0.15s;
  --fresh: #18c58b;
  --jira: #3aa1ff;
  --slack: #ec6dcb;
  --gmail: #ff7c7c;
  --urgent: #33114e;
  --needs-response: #d1b72f;
  --debug-info: #3aa1ff;
  --debug-error: #ff7c7c;
  --debug-surface: rgba(255, 255, 255, 0.92);
  --error-row-bg: rgba(255, 124, 124, 0.1);
  --held-stripe: repeating-linear-gradient(45deg, rgba(236, 109, 203, 0.12), rgba(236, 109, 203, 0.12) 4px, rgba(255, 255, 255, 0.58) 4px, rgba(255, 255, 255, 0.58) 8px);
}

/* ===== MIDNIGHT OPS ===== */

[data-theme="midnight-ops"][data-mode="dark"] {
  --bg: #0f0f0f;
  --card-bg: #1a1a1a;
  --surface: #111111;
  --surface-alt: #151515;
  --border: #ffffff;
  --border-subtle: #444444;
  --border-faint: #222222;
  --text: #ffffff;
  --muted: #888888;
  --hover-bg: #222222;
  --overlay-bg: rgba(0, 0, 0, 0.85);
  --shadow: 4px 4px 0 #ffffff;
  --shadow-sm: 2px 2px 0 #ffffff;
  --shadow-hover: 6px 6px 0 #ffffff;
  --font: 'JetBrains Mono', monospace;
  --font-heading: 'JetBrains Mono', monospace;
  --radius: 0;
  --radius-sm: 0;
  --transition-speed: 0.1s;
  --fresh: #00ff88;
  --jira: #4c9aff;
  --slack: #e01e5a;
  --gmail: #ea4335;
  --urgent: #ffffff;
  --needs-response: #f5f500;
  --debug-info: #4c9aff;
  --debug-error: #ff7b72;
  --debug-surface: rgba(10, 10, 10, 0.97);
  --error-row-bg: rgba(234, 67, 53, 0.08);
  --held-stripe: repeating-linear-gradient(45deg, #333333, #333333 4px, #1a1a1a 4px, #1a1a1a 8px);
}

[data-theme="midnight-ops"][data-mode="light"] {
  --bg: #f5f0eb;
  --card-bg: #ffffff;
  --surface: #f0ebe5;
  --surface-alt: #e8e3dd;
  --border: #000000;
  --border-subtle: #bdb4aa;
  --border-faint: #d9d1c8;
  --text: #000000;
  --muted: #655d56;
  --hover-bg: #ece4db;
  --overlay-bg: rgba(245, 240, 235, 0.92);
  --shadow: 4px 4px 0 #000000;
  --shadow-sm: 2px 2px 0 #000000;
  --shadow-hover: 6px 6px 0 #000000;
  --font: 'JetBrains Mono', monospace;
  --font-heading: 'JetBrains Mono', monospace;
  --radius: 0;
  --radius-sm: 0;
  --transition-speed: 0.1s;
  --fresh: #00894a;
  --jira: #0f62c9;
  --slack: #c7134c;
  --gmail: #c53f32;
  --urgent: #000000;
  --needs-response: #b39500;
  --debug-info: #0f62c9;
  --debug-error: #c53f32;
  --debug-surface: rgba(255, 255, 255, 0.97);
  --error-row-bg: rgba(197, 63, 50, 0.1);
  --held-stripe: repeating-linear-gradient(45deg, #ddd2c8, #ddd2c8 4px, #ffffff 4px, #ffffff 8px);
}

/* ===== SOFT KITTY ===== */

[data-theme="soft-kitty"][data-mode="dark"] {
  --bg: #1a1528;
  --card-bg: #241e35;
  --surface: #1f1830;
  --surface-alt: #2a2240;
  --border: #f4a8c8;
  --border-subtle: #554170;
  --border-faint: #382b4f;
  --text: #f7eef9;
  --muted: #b5a0cd;
  --hover-bg: #31254a;
  --overlay-bg: rgba(26, 21, 40, 0.9);
  --shadow: 0 12px 28px rgba(244, 168, 200, 0.18);
  --shadow-sm: 0 8px 18px rgba(244, 168, 200, 0.14);
  --shadow-hover: 0 18px 32px rgba(244, 168, 200, 0.24);
  --font: 'Comfortaa', sans-serif;
  --font-heading: 'Patrick Hand', cursive;
  --radius: 18px;
  --radius-sm: 12px;
  --transition-speed: 0.18s;
  --fresh: #90e3b2;
  --jira: #9ac4ff;
  --slack: #ff8ab2;
  --gmail: #ff9b87;
  --urgent: #f7eef9;
  --needs-response: #ffe38b;
  --debug-info: #9ac4ff;
  --debug-error: #ff9b87;
  --debug-surface: rgba(29, 23, 44, 0.97);
  --error-row-bg: rgba(255, 155, 135, 0.12);
  --held-stripe: repeating-linear-gradient(45deg, #332747, #332747 4px, #241e35 4px, #241e35 8px);
}

[data-theme="soft-kitty"][data-mode="light"] {
  --bg: #fff5f0;
  --card-bg: #ffffff;
  --surface: #fff0ea;
  --surface-alt: #ffe7df;
  --border: #f28aa8;
  --border-subtle: #edbfd0;
  --border-faint: #f6d7e1;
  --text: #40263e;
  --muted: #9f7890;
  --hover-bg: #ffe9ee;
  --overlay-bg: rgba(255, 245, 240, 0.94);
  --shadow: 0 12px 28px rgba(242, 138, 168, 0.16);
  --shadow-sm: 0 8px 18px rgba(242, 138, 168, 0.12);
  --shadow-hover: 0 18px 32px rgba(242, 138, 168, 0.22);
  --font: 'Comfortaa', sans-serif;
  --font-heading: 'Patrick Hand', cursive;
  --radius: 18px;
  --radius-sm: 12px;
  --transition-speed: 0.18s;
  --fresh: #3fb57b;
  --jira: #4f8fe6;
  --slack: #e65c89;
  --gmail: #e56b5d;
  --urgent: #40263e;
  --needs-response: #d7a92b;
  --debug-info: #4f8fe6;
  --debug-error: #e56b5d;
  --debug-surface: rgba(255, 255, 255, 0.97);
  --error-row-bg: rgba(229, 107, 93, 0.1);
  --held-stripe: repeating-linear-gradient(45deg, #fde0e8, #fde0e8 4px, #ffffff 4px, #ffffff 8px);
}
```

**Step 2: Update `tokens.css` to use theme variables as defaults**

Replace the existing `tokens.css` content so it references the theme CSS variables with fallbacks. Keep the existing variable names (`--bg-deep`, `--accent-pink`, etc.) mapped to the theme variables (`--bg`, `--border`, etc.) so existing components don't break:

```css
:root {
  /* Map Wave 1 token names to theme variables (with fallbacks for safety) */
  --bg-deep: var(--bg, #0d0221);
  --bg-surface: var(--card-bg, #150535);
  --bg-glass: var(--surface, rgba(36, 24, 50, 0.7));
  --bg-glass-hover: var(--hover-bg, rgba(36, 24, 50, 0.85));

  --accent-pink: var(--slack, #f4a8c8);
  --accent-mint: var(--fresh, #90e3b2);
  --accent-blue: var(--jira, #9ac4ff);
  --accent-coral: var(--gmail, #ff9b87);
  --accent-yellow: var(--needs-response, #f5d97e);

  --text-primary: var(--text, #f0e6ff);
  --text-muted: var(--muted, #8b7a9e);

  --radius-card: var(--radius, 16px);
  --radius-button: var(--radius-sm, 10px);
  --radius-badge: 6px;
  --glow-pink: 0 0 20px rgba(244, 168, 200, 0.3);
  --glow-mint: 0 0 20px rgba(144, 227, 178, 0.3);
  --glow-blue: 0 0 20px rgba(154, 196, 255, 0.3);
  --glow-coral: 0 0 20px rgba(255, 155, 135, 0.3);

  --source-gmail: var(--gmail, var(--accent-pink));
  --source-slack: var(--slack, var(--accent-mint));
  --source-jira: var(--jira, var(--accent-blue));
  --source-freshservice: var(--accent-coral);
  --source-calendar: var(--needs-response, var(--accent-yellow));

  --font-body: var(--font, 'Nunito', sans-serif);
  --font-mono: 'JetBrains Mono', monospace;
}
```

**Step 3: Import `themes.css` in `global.css`**

Add this import at the top of `dashboard/frontend/src/theme/global.css`:

```css
@import './themes.css';
```

Also add to `global.css` body section:

```css
body {
  background-color: var(--bg, var(--bg-deep));
  color: var(--text, var(--text-primary));
  font-family: var(--font, var(--font-body));
}
```

**Step 4: Set default theme attributes on index.html**

Modify `dashboard/frontend/index.html` — add attributes to the `<html>` tag:

```html
<html lang="en" data-theme="neon-dreams" data-mode="dark">
```

**Step 5: Verify theme switching works manually**

Open browser devtools on the running dev server, change `data-theme` attribute on `<html>` to `"soft-kitty"` — colors should change immediately.

**Step 6: Commit**

```bash
git add dashboard/frontend/src/theme/ dashboard/frontend/index.html
git commit -m "Add 6-theme CSS variable system with attribute-based switching"
```

---

### Task 3: Zustand stores — toast, debug, extend UI

**Files:**
- Modify: `dashboard/frontend/src/stores/ui.ts`
- Create: `dashboard/frontend/src/stores/toast.ts`
- Create: `dashboard/frontend/src/stores/debug.ts`
- Create: `dashboard/frontend/src/stores/__tests__/toast.test.ts`
- Create: `dashboard/frontend/src/stores/__tests__/debug.test.ts`

**Step 1: Write failing tests for toast store**

Create `dashboard/frontend/src/stores/__tests__/toast.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useToastStore } from '../toast'

beforeEach(() => useToastStore.getState().clear())

describe('useToastStore', () => {
  it('adds a toast with auto-generated id', () => {
    useToastStore.getState().addToast('Hello', 'success')
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0].message).toBe('Hello')
    expect(toasts[0].level).toBe('success')
    expect(toasts[0].id).toBeDefined()
  })

  it('removes a toast by id', () => {
    useToastStore.getState().addToast('A', 'info')
    const id = useToastStore.getState().toasts[0].id
    useToastStore.getState().removeToast(id)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('clears all toasts', () => {
    useToastStore.getState().addToast('A', 'info')
    useToastStore.getState().addToast('B', 'error')
    useToastStore.getState().clear()
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/stores/__tests__/toast.test.ts
```

Expected: FAIL — module `../toast` not found

**Step 3: Implement toast store**

Create `dashboard/frontend/src/stores/toast.ts`:

```typescript
import { create } from 'zustand'

export type ToastLevel = 'success' | 'error' | 'info'

export interface Toast {
  id: string
  message: string
  level: ToastLevel
}

interface ToastState {
  toasts: Toast[]
  addToast: (message: string, level: ToastLevel) => void
  removeToast: (id: string) => void
  clear: () => void
}

let nextId = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (message, level) => {
    const id = `toast-${++nextId}`
    set((s) => ({ toasts: [...s.toasts, { id, message, level }] }))
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
    }, 4000)
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}))
```

**Step 4: Run toast test**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/stores/__tests__/toast.test.ts
```

Expected: PASS

**Step 5: Write failing tests for debug store**

Create `dashboard/frontend/src/stores/__tests__/debug.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useDebugStore } from '../debug'

beforeEach(() => useDebugStore.getState().clear())

describe('useDebugStore', () => {
  it('adds a debug entry', () => {
    useDebugStore.getState().addEntry('info', 'GET /api/cards', { status: 200, duration: 45 })
    const entries = useDebugStore.getState().entries
    expect(entries).toHaveLength(1)
    expect(entries[0].level).toBe('info')
    expect(entries[0].message).toBe('GET /api/cards')
  })

  it('limits to 150 entries', () => {
    for (let i = 0; i < 160; i++) {
      useDebugStore.getState().addEntry('info', `entry ${i}`)
    }
    expect(useDebugStore.getState().entries).toHaveLength(150)
  })

  it('toggles drawer open state', () => {
    expect(useDebugStore.getState().isOpen).toBe(false)
    useDebugStore.getState().toggle()
    expect(useDebugStore.getState().isOpen).toBe(true)
  })
})
```

**Step 6: Implement debug store**

Create `dashboard/frontend/src/stores/debug.ts`:

```typescript
import { create } from 'zustand'

export type DebugLevel = 'info' | 'warn' | 'error'

export interface DebugEntry {
  id: number
  level: DebugLevel
  message: string
  details?: Record<string, unknown>
  timestamp: string
  sentToClaude: boolean
}

interface DebugState {
  entries: DebugEntry[]
  isOpen: boolean
  addEntry: (level: DebugLevel, message: string, details?: Record<string, unknown>) => void
  markSent: (id: number) => void
  toggle: () => void
  clear: () => void
}

const MAX_ENTRIES = 150
let nextId = 0

export const useDebugStore = create<DebugState>((set) => ({
  entries: [],
  isOpen: false,
  addEntry: (level, message, details) => {
    const entry: DebugEntry = {
      id: ++nextId,
      level,
      message,
      details,
      timestamp: new Date().toISOString(),
      sentToClaude: false,
    }
    set((s) => ({
      entries: [entry, ...s.entries].slice(0, MAX_ENTRIES),
    }))
  },
  markSent: (id) =>
    set((s) => ({
      entries: s.entries.map((e) => (e.id === id ? { ...e, sentToClaude: true } : e)),
    })),
  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
  clear: () => set({ entries: [] }),
}))
```

**Step 7: Run debug test**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/stores/__tests__/debug.test.ts
```

Expected: PASS

**Step 8: Extend UI store with theme, mode, terminal**

Modify `dashboard/frontend/src/stores/ui.ts`:

```typescript
import { create } from 'zustand'
import type { CardSource } from '../api/types'

export type ThemeName = 'neon-dreams' | 'midnight-ops' | 'soft-kitty'
export type ModeName = 'dark' | 'light'
export type TerminalName = 'Terminal' | 'Warp' | 'iTerm' | 'Alacritty' | 'kitty'

interface UIState {
  activeSource: CardSource
  activeCardId: number | null
  expandedActions: Set<number>
  theme: ThemeName
  mode: ModeName
  terminal: TerminalName
  macosNotifications: boolean
  setActiveSource: (source: CardSource) => void
  setActiveCard: (id: number | null) => void
  toggleExpandedActions: (id: number) => void
  setTheme: (theme: ThemeName) => void
  setMode: (mode: ModeName) => void
  toggleMode: () => void
  setTerminal: (terminal: TerminalName) => void
  setMacosNotifications: (enabled: boolean) => void
  hydrateSettings: (settings: { theme?: string; mode?: string; terminal?: string; macos_notifications?: boolean }) => void
}

function applyThemeToDOM(theme: ThemeName, mode: ModeName) {
  document.documentElement.setAttribute('data-theme', theme)
  document.documentElement.setAttribute('data-mode', mode)
  localStorage.setItem('eb-theme', theme)
  localStorage.setItem('eb-mode', mode)
}

export const useUIStore = create<UIState>((set, get) => ({
  activeSource: 'all',
  activeCardId: null,
  expandedActions: new Set(),
  theme: (localStorage.getItem('eb-theme') as ThemeName) || 'neon-dreams',
  mode: (localStorage.getItem('eb-mode') as ModeName) || 'dark',
  terminal: 'Terminal',
  macosNotifications: false,

  setActiveSource: (source) => set({ activeSource: source }),
  setActiveCard: (id) => set({ activeCardId: id }),
  toggleExpandedActions: (id) =>
    set((state) => {
      const next = new Set(state.expandedActions)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { expandedActions: next }
    }),
  setTheme: (theme) => {
    set({ theme })
    applyThemeToDOM(theme, get().mode)
  },
  setMode: (mode) => {
    set({ mode })
    applyThemeToDOM(get().theme, mode)
  },
  toggleMode: () => {
    const next = get().mode === 'dark' ? 'light' : 'dark'
    set({ mode: next })
    applyThemeToDOM(get().theme, next)
  },
  setTerminal: (terminal) => set({ terminal }),
  setMacosNotifications: (enabled) => set({ macosNotifications: enabled }),
  hydrateSettings: (s) => {
    const theme = (['neon-dreams', 'midnight-ops', 'soft-kitty'].includes(s.theme ?? '') ? s.theme : get().theme) as ThemeName
    const mode = (['dark', 'light'].includes(s.mode ?? '') ? s.mode : get().mode) as ModeName
    const terminal = (['Terminal', 'Warp', 'iTerm', 'Alacritty', 'kitty'].includes(s.terminal ?? '') ? s.terminal : get().terminal) as TerminalName
    set({ theme, mode, terminal, macosNotifications: s.macos_notifications ?? false })
    applyThemeToDOM(theme, mode)
  },
}))
```

**Step 9: Run existing UI store test to check no regression**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/stores/__tests__/ui.test.ts
```

Expected: PASS

**Step 10: Commit**

```bash
git add dashboard/frontend/src/stores/
git commit -m "Add toast and debug Zustand stores, extend UI store with theme/mode/terminal"
```

---

### Task 4: API types and client extensions

**Files:**
- Modify: `dashboard/frontend/src/api/types.ts`
- Modify: `dashboard/frontend/src/api/client.ts`
- Create: `dashboard/frontend/src/api/__tests__/client-wave2.test.ts`

**Step 1: Extend types.ts with all missing types**

Add these types to the end of `dashboard/frontend/src/api/types.ts`:

```typescript
export interface SettingsResponse {
  terminal: string
  macos_notifications: boolean
  theme: string
  mode: string
}

export interface DecisionResponse {
  card_id?: number
  task_number?: number
  action: string
  decision: string
  decision_event_id: number
  action_step_id: number
}

export interface CloseResponse {
  card_id?: number
  task_number?: number
  status: string
  daily_file: string
  entry: string
  inserted: boolean
  decision_event_id: number
  action_step_id: number
}

export interface JiraWriteResponse {
  card_id?: number
  task_number?: number
  issue_key: string
  output: unknown
  decision_event_id: number
  action_step_id: number
}

export interface SendDraftResponse {
  status: string
  output: string
  decision_event_id: number
  action_step_id: number
}

export interface GmailAnalyzeResponse {
  card_id: number
  detected_category: string
  suggested_labels: string[]
  reasoning: string
  draft_response: string
}

export interface RefineResponse {
  response: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatHistoryResponse {
  card_id?: number
  task_number?: number
  messages: ChatMessage[]
}

export interface Task {
  number: number
  title: string
  status: string
  priority: string
  description: string
  jira_keys?: string[]
  related_card_ids?: number[]
}

export interface TasksResponse {
  tasks: Task[]
}

export interface JiraSprint {
  issues: JiraIssue[]
}

export interface JiraIssue {
  key: string
  summary: string
  status: string
  assignee: string
  priority: string
}

export interface DailyLog {
  date: string
  content: string
  stats?: Record<string, unknown>
}

export interface DailyLogsResponse {
  logs: string[]
}

export interface KnowledgeDoc {
  path: string
  group: string
  name: string
}

export interface KnowledgeIndexResponse {
  documents: KnowledgeDoc[]
}

export interface BriefingResponse {
  cognitive_load: string
  meetings: Array<{ time: string; title: string; hangout_link?: string; prep_notes?: string }>
  needs_response: Array<{ summary: string; source: string; has_draft: boolean }>
  alerts: Array<{ type: string; message: string }>
  stats: { drafts_sent: number; triaged: number; time_saved_minutes: number }
  pep_talk: string
}

export interface SuggestionCard extends Card {
  suggestion_prompt?: string
}

export interface PlanStep {
  index: number
  summary: string
  status: string
  tool: string
  params: Record<string, unknown>
  draft_content?: string
}

export interface PlanPhase {
  name: string
  steps: PlanStep[]
}

export interface PlanResponse {
  plan: {
    card_id: number
    status: string
    phases: PlanPhase[]
  }
}

export interface PlaybookDraft {
  id: string
  name: string
  trigger: string
  confidence: number
  steps: Array<{ summary: string; tool: string }>
}

export interface Playbook extends PlaybookDraft {
  executions: number
}

export interface RestartResponse {
  status: string
  mode: string
  manager: string
}

export interface RestartStatusResponse {
  phase: string
  message: string
  updated_at: string | null
}

export interface OpenSessionResponse {
  status: string
  terminal: string
  launcher: string
  chat_session_id: number
}

export type TabRoute = 'inbox' | 'tasks' | 'jira' | 'calendar' | 'daily' | 'learnings' | 'knowledge' | 'suggestions' | 'playbooks'
```

**Step 2: Extend client.ts with all missing API functions**

Add these functions to `dashboard/frontend/src/api/client.ts`:

```typescript
import type {
  CardsResponse, InboxViewResponse, CardSource, SettingsResponse,
  DecisionResponse, RefineResponse, ChatHistoryResponse, TasksResponse,
  JiraSprint, DailyLogsResponse, DailyLog, KnowledgeIndexResponse,
  BriefingResponse, PlanResponse, RestartResponse, RestartStatusResponse,
  PollersResponse, OpenSessionResponse, GmailAnalyzeResponse,
} from './types'

// ... keep existing request, fetchCards, fetchInboxView, performCardAction, fetchHealth ...

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

export async function postDecision(
  entityType: 'cards' | 'tasks',
  entityId: number,
  action: string,
  decision: string,
  rationale: string = '',
): Promise<DecisionResponse> {
  return request<DecisionResponse>(`/api/${entityType}/${entityId}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, decision, rationale }),
  })
}

export async function fetchChatHistory(entityType: 'cards' | 'tasks', entityId: number): Promise<ChatHistoryResponse> {
  return request<ChatHistoryResponse>(`/api/${entityType}/${entityId}/chat-history`)
}

export async function postRefine(
  entityType: 'cards' | 'tasks',
  entityId: number,
  message: string,
  history: Array<{ role: string; content: string }> = [],
): Promise<RefineResponse> {
  return request<RefineResponse>(`/api/${entityType}/${entityId}/refine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
}

export async function fetchTasks(): Promise<TasksResponse> {
  return request<TasksResponse>('/api/tasks')
}

export async function fetchJiraSprint(refresh = false): Promise<JiraSprint> {
  return request<JiraSprint>(`/api/jira/sprint${refresh ? '?refresh=true' : ''}`)
}

export async function fetchDailyLogs(): Promise<DailyLogsResponse> {
  return request<DailyLogsResponse>('/api/daily/logs')
}

export async function fetchDailyLog(date: string): Promise<DailyLog> {
  return request<DailyLog>(`/api/daily/logs/${date}`)
}

export async function fetchLearningsSummary(range: string, date?: string): Promise<unknown> {
  const params = new URLSearchParams({ range })
  if (date) params.set('date', date)
  return request(`/api/learnings/summary?${params}`)
}

export async function fetchLearningsEvents(range: string, date?: string, limit = 200): Promise<unknown> {
  const params = new URLSearchParams({ range, limit: String(limit) })
  if (date) params.set('date', date)
  return request(`/api/learnings/events?${params}`)
}

export async function fetchKnowledgeIndex(): Promise<KnowledgeIndexResponse> {
  return request<KnowledgeIndexResponse>('/api/knowledge/index')
}

export async function fetchKnowledgeDoc(path: string): Promise<{ content: string }> {
  return request(`/api/knowledge/doc?path=${encodeURIComponent(path)}`)
}

export async function fetchBriefing(): Promise<BriefingResponse> {
  return request<BriefingResponse>('/api/briefing')
}

export async function fetchSuggestions(refresh = false): Promise<CardsResponse> {
  return request<CardsResponse>(`/api/suggestions${refresh ? '?refresh=true' : ''}`)
}

export async function fetchPlaybooks(): Promise<{ playbooks: unknown[] }> {
  return request('/api/playbooks')
}

export async function fetchPlaybookDrafts(): Promise<{ drafts: unknown[] }> {
  return request('/api/playbooks/drafts')
}

export async function executePlaybook(playbookId: string, ticketContext: unknown, approval: string): Promise<unknown> {
  return request('/api/playbooks/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ playbook_id: playbookId, ticket_context: ticketContext, approval }),
  })
}

export async function fetchPlan(cardId: number): Promise<PlanResponse> {
  return request<PlanResponse>(`/api/cards/${cardId}/plan`)
}

export async function fetchPollers(): Promise<PollersResponse> {
  return request<PollersResponse>('/api/pollers/status')
}

export async function syncPoller(pollerId: string): Promise<unknown> {
  return request(`/api/pollers/${pollerId}/sync`, { method: 'POST' })
}

export async function postRestart(): Promise<RestartResponse> {
  return request<RestartResponse>('/api/restart', { method: 'POST' })
}

export async function fetchRestartStatus(): Promise<RestartStatusResponse> {
  return request<RestartStatusResponse>('/api/restart-status')
}

export async function postNotify(title: string, message: string): Promise<unknown> {
  return request('/api/notify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, message }),
  })
}

export async function sendDebugToClaude(logLine: string, level: string, tab: string, details?: Record<string, unknown>): Promise<unknown> {
  return request('/api/debug/send-to-claude', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ log_line: logLine, level, tab, timestamp: new Date().toISOString(), details }),
  })
}

export async function openSession(entityType: 'cards' | 'tasks', entityId: number): Promise<OpenSessionResponse> {
  return request<OpenSessionResponse>(`/api/${entityType}/${entityId}/open-session`, { method: 'POST' })
}

export async function gmailAnalyze(cardId: number, includeLabels = true, includeDraft = true): Promise<GmailAnalyzeResponse> {
  return request<GmailAnalyzeResponse>(`/api/cards/${cardId}/gmail-analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ include_labels: includeLabels, include_draft: includeDraft }),
  })
}
```

**Step 3: Write a test for the new API functions**

Create `dashboard/frontend/src/api/__tests__/client-wave2.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchSettings, updateSettings, postDecision, fetchPollers, syncPoller, postRestart } from '../client'

const mockFetch = vi.fn()
global.fetch = mockFetch

beforeEach(() => mockFetch.mockReset())

describe('Wave 2 API client', () => {
  it('fetchSettings calls GET /api/settings', async () => {
    const mock = { terminal: 'Warp', theme: 'neon-dreams', mode: 'dark', macos_notifications: false }
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mock) })
    const result = await fetchSettings()
    expect(mockFetch).toHaveBeenCalledWith('/api/settings')
    expect(result).toEqual(mock)
  })

  it('updateSettings POSTs to /api/settings', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) })
    await updateSettings({ theme: 'soft-kitty' })
    expect(mockFetch).toHaveBeenCalledWith('/api/settings', expect.objectContaining({ method: 'POST' }))
  })

  it('postDecision POSTs to correct entity endpoint', async () => {
    const mock = { card_id: 1, action: 'hold', decision: 'rejected', decision_event_id: 42, action_step_id: 7 }
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mock) })
    const result = await postDecision('cards', 1, 'hold', 'rejected', 'not ready')
    expect(mockFetch).toHaveBeenCalledWith('/api/cards/1/decision', expect.objectContaining({ method: 'POST' }))
    expect(result.decision_event_id).toBe(42)
  })

  it('fetchPollers calls GET /api/pollers/status', async () => {
    const mock = { pollers: [], generated_at: '2026-01-01T00:00:00Z' }
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mock) })
    await fetchPollers()
    expect(mockFetch).toHaveBeenCalledWith('/api/pollers/status')
  })

  it('syncPoller POSTs to /api/pollers/{id}/sync', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ status: 'syncing' }) })
    await syncPoller('slack')
    expect(mockFetch).toHaveBeenCalledWith('/api/pollers/slack/sync', expect.objectContaining({ method: 'POST' }))
  })

  it('postRestart POSTs to /api/restart', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ status: 'restarting' }) })
    await postRestart()
    expect(mockFetch).toHaveBeenCalledWith('/api/restart', expect.objectContaining({ method: 'POST' }))
  })
})
```

**Step 4: Run tests**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run src/api/__tests__/client-wave2.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add dashboard/frontend/src/api/
git commit -m "Extend API types and client with all Wave 2 endpoints"
```

---

### Task 5: React Router setup and AppLayout shell

**Files:**
- Create: `dashboard/frontend/src/router.tsx`
- Create: `dashboard/frontend/src/layouts/AppLayout.tsx`
- Create: `dashboard/frontend/src/layouts/AppLayout.module.css`
- Modify: `dashboard/frontend/src/main.tsx`
- Modify: `dashboard/frontend/src/App.tsx`
- Modify: `dashboard/frontend/src/features/inbox/Sidebar.tsx`

**Step 1: Create the router config**

Create `dashboard/frontend/src/router.tsx`:

```typescript
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import App from './App'

// Lazy-load tab views (will be created in later tasks — placeholder for now)
const PlaceholderView = ({ name }: { name: string }) => (
  <div style={{ padding: '2rem', color: 'var(--text)', fontFamily: 'var(--font)' }}>
    {name} view — coming soon
  </div>
)

export const router = createBrowserRouter(
  [
    {
      path: '/app',
      element: <AppLayout />,
      children: [
        { index: true, element: <Navigate to="inbox" replace /> },
        { path: 'inbox', element: <App /> },
        { path: 'inbox/:source', element: <App /> },
        { path: 'tasks', element: <PlaceholderView name="Tasks" /> },
        { path: 'jira', element: <PlaceholderView name="Jira Sprint" /> },
        { path: 'calendar', element: <PlaceholderView name="Calendar" /> },
        { path: 'daily', element: <PlaceholderView name="Daily Log" /> },
        { path: 'learnings', element: <PlaceholderView name="Learnings" /> },
        { path: 'knowledge', element: <PlaceholderView name="Knowledge" /> },
        { path: 'suggestions', element: <PlaceholderView name="Suggestions" /> },
        { path: 'playbooks', element: <PlaceholderView name="Playbooks" /> },
      ],
    },
  ],
  { basename: '/' },
)
```

**Step 2: Create the AppLayout shell**

Create `dashboard/frontend/src/layouts/AppLayout.tsx`:

```typescript
import { Outlet } from 'react-router-dom'
import { useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useSSE } from '../hooks/useSSE'
import type { SSEEvent } from '../hooks/useSSE'
import { Header } from '../features/inbox/Header'
import { Sidebar } from '../features/inbox/Sidebar'
import styles from './AppLayout.module.css'

const particles = ['\u273f', '\u22c6', '\u2661', '\u2727', '\u273f', '\u22c6', '\u2661', '\u2727']

export function AppLayout() {
  const queryClient = useQueryClient()

  const handleSSE = useCallback(
    (_event: SSEEvent) => {
      queryClient.invalidateQueries({ queryKey: ['cards'] })
    },
    [queryClient],
  )

  useSSE(handleSSE)

  return (
    <div className={styles.layout}>
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

      <Header pendingCount={0} isLoading={false} />

      <div className={styles.body}>
        <Sidebar />
        <div className={styles.content}>
          <Outlet />
        </div>
      </div>
    </div>
  )
}
```

Create `dashboard/frontend/src/layouts/AppLayout.module.css` — copy the existing `App.module.css` layout styles.

**Step 3: Convert Sidebar to use NavLink**

Modify `dashboard/frontend/src/features/inbox/Sidebar.tsx` to use React Router `NavLink` instead of Zustand source filter:

```typescript
import { NavLink } from 'react-router-dom'
import styles from './Sidebar.module.css'

const navItems = [
  { to: '/app/inbox', label: 'Inbox' },
  { to: '/app/tasks', label: 'Tasks' },
  { to: '/app/jira', label: 'Jira' },
  { to: '/app/calendar', label: 'Calendar' },
  { to: '/app/daily', label: 'Daily' },
  { to: '/app/learnings', label: 'Learnings' },
  { to: '/app/knowledge', label: 'Knowledge' },
  { to: '/app/suggestions', label: 'Suggestions' },
  { to: '/app/playbooks', label: 'Playbooks' },
]

export function Sidebar() {
  return (
    <nav className={styles.sidebar}>
      {navItems.map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => `${styles.item} ${isActive ? styles.active : ''}`}
        >
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
```

**Step 4: Refactor App.tsx to be the Inbox route component**

Strip the layout shell from `App.tsx` — it now only renders the inbox content (StatsBar + CardList). The layout is handled by `AppLayout`. Also read the `:source` route param.

```typescript
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useCards } from './hooks/useCards'
import { StatsBar } from './features/stats/StatsBar'
import { CardList } from './features/inbox/CardList'
import type { CardSource } from './api/types'

export default function App() {
  const { source } = useParams<{ source?: string }>()
  const activeSource: CardSource = (source as CardSource) || 'all'
  const { data, isLoading } = useCards(activeSource)

  const counts = data?.counts ?? { pending: 0, held: 0, approved: 0, completed: 0, failed: 0 }

  return (
    <>
      <StatsBar
        needsAction={counts.pending}
        autoResolved={counts.completed}
        draftAcceptRate={(counts.approved + counts.failed) > 0 ? Math.round((counts.approved / (counts.approved + counts.failed)) * 100) : 0}
        timeSavedMinutes={counts.completed * 5}
      />
      <CardList source={activeSource} />
    </>
  )
}
```

Update `CardList` to accept an optional `source` prop instead of reading from Zustand.

**Step 5: Update main.tsx to use RouterProvider**

```typescript
import './theme/global.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { router } from './router'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 3, staleTime: 30_000 },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
```

**Step 6: Build and verify**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run build
```

Expected: Build succeeds, output in `../static-react/`

**Step 7: Run existing tests — fix any imports**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run
```

Fix any import path issues caused by refactoring. The existing Sidebar test will need updating since Sidebar no longer accepts props.

**Step 8: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add React Router with AppLayout shell and tab navigation"
```

---

### Task 6: Header controls — ThemePicker, ModeToggle, TerminalPicker

**Files:**
- Create: `dashboard/frontend/src/features/header/ThemePicker.tsx`
- Create: `dashboard/frontend/src/features/header/ModeToggle.tsx`
- Create: `dashboard/frontend/src/features/header/TerminalPicker.tsx`
- Create: `dashboard/frontend/src/features/header/Header.module.css`
- Create: `dashboard/frontend/src/hooks/useSettings.ts`
- Modify: `dashboard/frontend/src/features/inbox/Header.tsx`

**Step 1: Create useSettings hook**

Create `dashboard/frontend/src/hooks/useSettings.ts`:

```typescript
import { useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchSettings, updateSettings } from '../api/client'
import { useUIStore } from '../stores/ui'
import type { SettingsResponse } from '../api/types'

export function useSettings() {
  const hydrateSettings = useUIStore((s) => s.hydrateSettings)

  const query = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (query.data) {
      hydrateSettings(query.data)
    }
  }, [query.data, hydrateSettings])

  return query
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: Partial<SettingsResponse>) => updateSettings(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  })
}
```

**Step 2: Create ThemePicker**

Create `dashboard/frontend/src/features/header/ThemePicker.tsx`:

```typescript
import { useUIStore } from '../../stores/ui'
import { useUpdateSettings } from '../../hooks/useSettings'
import type { ThemeName } from '../../stores/ui'

const themes: { value: ThemeName; label: string }[] = [
  { value: 'neon-dreams', label: 'Neon Dreams' },
  { value: 'midnight-ops', label: 'Midnight Ops' },
  { value: 'soft-kitty', label: 'Soft Kitty' },
]

export function ThemePicker() {
  const theme = useUIStore((s) => s.theme)
  const setTheme = useUIStore((s) => s.setTheme)
  const update = useUpdateSettings()

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value as ThemeName
    setTheme(value)
    update.mutate({ theme: value })
  }

  return (
    <select value={theme} onChange={handleChange} aria-label="Theme">
      {themes.map((t) => (
        <option key={t.value} value={t.value}>{t.label}</option>
      ))}
    </select>
  )
}
```

**Step 3: Create ModeToggle**

Create `dashboard/frontend/src/features/header/ModeToggle.tsx`:

```typescript
import { useUIStore } from '../../stores/ui'
import { useUpdateSettings } from '../../hooks/useSettings'

export function ModeToggle() {
  const mode = useUIStore((s) => s.mode)
  const toggleMode = useUIStore((s) => s.toggleMode)
  const update = useUpdateSettings()

  const handleClick = () => {
    const nextMode = mode === 'dark' ? 'light' : 'dark'
    toggleMode()
    update.mutate({ mode: nextMode })
  }

  return (
    <button onClick={handleClick} aria-label="Toggle light and dark mode" type="button">
      {mode === 'dark' ? '\u263E' : '\u2600'}
    </button>
  )
}
```

**Step 4: Create TerminalPicker**

Create `dashboard/frontend/src/features/header/TerminalPicker.tsx`:

```typescript
import { useUIStore } from '../../stores/ui'
import { useUpdateSettings } from '../../hooks/useSettings'
import type { TerminalName } from '../../stores/ui'

const terminals: TerminalName[] = ['Terminal', 'Warp', 'iTerm', 'Alacritty', 'kitty']

export function TerminalPicker() {
  const terminal = useUIStore((s) => s.terminal)
  const setTerminal = useUIStore((s) => s.setTerminal)
  const update = useUpdateSettings()

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value as TerminalName
    setTerminal(value)
    update.mutate({ terminal: value })
  }

  return (
    <select value={terminal} onChange={handleChange} aria-label="Terminal">
      {terminals.map((t) => (
        <option key={t} value={t}>{t}</option>
      ))}
    </select>
  )
}
```

**Step 5: Update Header to include all controls**

Modify `dashboard/frontend/src/features/inbox/Header.tsx` to include the new controls:

```typescript
import { ChibiMascot } from '../../components/ChibiMascot'
import type { MascotMood } from '../../components/ChibiMascot'
import { ThemePicker } from '../header/ThemePicker'
import { ModeToggle } from '../header/ModeToggle'
import { TerminalPicker } from '../header/TerminalPicker'
import { useSettings } from '../../hooks/useSettings'
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
  useSettings() // hydrate settings on mount

  return (
    <header className={styles.header}>
      <div className={styles.titleGroup}>
        <ChibiMascot mood={getMood(pendingCount, isLoading)} size={40} />
        <span className={styles.title}>ENG-BUDDY</span>
      </div>
      <div className={styles.controls}>
        <ThemePicker />
        <ModeToggle />
        <TerminalPicker />
      </div>
    </header>
  )
}
```

**Step 6: Build and verify**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run build
```

**Step 7: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add ThemePicker, ModeToggle, TerminalPicker header controls with settings persistence"
```

---

### Task 7: Header controls — RestartButton, PollerTimers, NotificationToggle

**Files:**
- Create: `dashboard/frontend/src/features/header/RestartButton.tsx`
- Create: `dashboard/frontend/src/features/header/PollerTimers.tsx`
- Create: `dashboard/frontend/src/features/header/NotificationToggle.tsx`
- Create: `dashboard/frontend/src/hooks/usePollerCountdown.ts`

**Step 1: Create usePollerCountdown hook**

Create `dashboard/frontend/src/hooks/usePollerCountdown.ts`:

```typescript
import { useState, useEffect } from 'react'
import type { Poller } from '../api/types'

export function usePollerCountdown(pollers: Poller[]): Map<string, number | null> {
  const [countdowns, setCountdowns] = useState<Map<string, number | null>>(new Map())

  useEffect(() => {
    const calc = () => {
      const now = Date.now()
      const next = new Map<string, number | null>()
      for (const p of pollers) {
        if (!p.next_run_at) { next.set(p.id, null); continue }
        const target = new Date(p.next_run_at).getTime()
        let diff = Math.round((target - now) / 1000)
        if (diff < 0 && p.interval_seconds > 0) {
          const cycles = Math.ceil(Math.abs(diff) / p.interval_seconds)
          diff += cycles * p.interval_seconds
        }
        next.set(p.id, Math.max(0, diff))
      }
      setCountdowns(next)
    }
    calc()
    const id = setInterval(calc, 1000)
    return () => clearInterval(id)
  }, [pollers])

  return countdowns
}
```

**Step 2: Create PollerTimers**

Create `dashboard/frontend/src/features/header/PollerTimers.tsx`:

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPollers, syncPoller } from '../../api/client'
import { usePollerCountdown } from '../../hooks/usePollerCountdown'
import styles from './PollerTimers.module.css'

export function PollerTimers() {
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['pollers'],
    queryFn: fetchPollers,
    refetchInterval: 30_000,
  })

  const pollers = data?.pollers ?? []
  const countdowns = usePollerCountdown(pollers)

  const sync = useMutation({
    mutationFn: (id: string) => syncPoller(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pollers'] }),
  })

  const formatCountdown = (seconds: number | null | undefined): string => {
    if (seconds == null) return '--'
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  return (
    <div className={styles.timers} aria-live="polite">
      {pollers.map((p) => (
        <button
          key={p.id}
          className={`${styles.badge} ${styles[p.health] ?? ''}`}
          onClick={() => sync.mutate(p.id)}
          title={`Click to sync ${p.label} now`}
          disabled={sync.isPending}
        >
          {p.label} {formatCountdown(countdowns.get(p.id))}
        </button>
      ))}
    </div>
  )
}
```

Create `dashboard/frontend/src/features/header/PollerTimers.module.css`:

```css
.timers {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.badge {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  padding: 2px 8px;
  border: 1px solid var(--border-subtle);
  background: var(--surface, var(--bg-glass));
  color: var(--text, var(--text-primary));
  border-radius: var(--radius-badge, 6px);
  cursor: pointer;
  transition: background var(--transition-speed, 0.15s);
}

.badge:hover {
  background: var(--hover-bg, var(--bg-glass-hover));
}

.healthy { border-color: var(--fresh); }
.warning { border-color: var(--needs-response); }
.error { border-color: var(--gmail); }
.syncing { opacity: 0.6; }
```

**Step 3: Create RestartButton**

Create `dashboard/frontend/src/features/header/RestartButton.tsx`:

```typescript
import { useState, useRef, useCallback } from 'react'
import { postRestart, fetchHealth, fetchRestartStatus } from '../../api/client'

type Phase = 'idle' | 'restarting' | 'syncing' | 'complete' | 'failed' | 'timeout'

const LABELS: Record<Phase, string> = {
  idle: 'RESTART',
  restarting: 'RESTARTING...',
  syncing: 'SYNCING DATA...',
  complete: 'RESTART',
  failed: 'RESTART FAILED',
  timeout: 'RESTART TIMEOUT',
}

export function RestartButton() {
  const [phase, setPhase] = useState<Phase>('idle')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  const handleClick = useCallback(async () => {
    if (phase === 'restarting' || phase === 'syncing') return
    setPhase('restarting')

    try {
      await postRestart()
    } catch {
      setPhase('failed')
      return
    }

    const deadline = Date.now() + 120_000

    const pollHealth = async (): Promise<boolean> => {
      while (Date.now() < deadline) {
        try {
          await fetchHealth()
          return true
        } catch {
          await new Promise((r) => { timerRef.current = setTimeout(r, 500) })
        }
      }
      return false
    }

    const healthy = await pollHealth()
    if (!healthy) { setPhase('timeout'); return }

    setPhase('syncing')

    const pollStatus = async () => {
      while (Date.now() < deadline) {
        try {
          const status = await fetchRestartStatus()
          if (status.phase === 'complete' || status.phase === 'idle') {
            setPhase('complete')
            setTimeout(() => setPhase('idle'), 2000)
            return
          }
        } catch { /* server still coming up */ }
        await new Promise((r) => { timerRef.current = setTimeout(r, 500) })
      }
      setPhase('timeout')
    }

    await pollStatus()
  }, [phase])

  const busy = phase === 'restarting' || phase === 'syncing'

  return (
    <button onClick={handleClick} disabled={busy} aria-label="Restart dashboard">
      {LABELS[phase]}
    </button>
  )
}
```

**Step 4: Create NotificationToggle**

Create `dashboard/frontend/src/features/header/NotificationToggle.tsx`:

```typescript
import { useUIStore } from '../../stores/ui'
import { useUpdateSettings } from '../../hooks/useSettings'

export function NotificationToggle() {
  const enabled = useUIStore((s) => s.macosNotifications)
  const setEnabled = useUIStore((s) => s.setMacosNotifications)
  const update = useUpdateSettings()

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEnabled(e.target.checked)
    update.mutate({ macos_notifications: e.target.checked })
  }

  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem', color: 'var(--muted)' }}>
      <input type="checkbox" checked={enabled} onChange={handleChange} />
      Notify
    </label>
  )
}
```

**Step 5: Wire all controls into Header**

Update `Header.tsx` to include `RestartButton`, `PollerTimers`, `NotificationToggle`.

**Step 6: Build and verify**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run build
```

**Step 7: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add RestartButton, PollerTimers, NotificationToggle header controls"
```

---

### Task 8: Card ActionTray with decision flow

**Files:**
- Create: `dashboard/frontend/src/features/inbox/ActionTray.tsx`
- Create: `dashboard/frontend/src/features/inbox/ActionTray.module.css`
- Create: `dashboard/frontend/src/features/inbox/InlineConfirm.tsx`
- Create: `dashboard/frontend/src/hooks/useCardDecision.ts`
- Modify: `dashboard/frontend/src/features/inbox/CardItem.tsx`

**Step 1: Create useCardDecision hook**

Create `dashboard/frontend/src/hooks/useCardDecision.ts`:

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postDecision, performCardAction } from '../api/client'
import { useToastStore } from '../stores/toast'

interface DecisionAction {
  cardId: number
  action: string
  decision: 'approved' | 'rejected' | 'refined'
  rationale?: string
  followUp?: { endpoint: string; body?: Record<string, unknown> }
}

export function useCardDecision() {
  const queryClient = useQueryClient()
  const addToast = useToastStore((s) => s.addToast)

  return useMutation({
    mutationFn: async ({ cardId, action, decision, rationale, followUp }: DecisionAction) => {
      const result = await postDecision('cards', cardId, action, decision, rationale)
      if (followUp) {
        const body = { ...followUp.body, decision_event_id: result.decision_event_id }
        await performCardAction(cardId, followUp.endpoint, body)
      }
      return result
    },
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['cards'] })
      addToast(`Card #${vars.cardId}: ${vars.action} ${vars.decision}`, 'success')
    },
    onError: (_err, vars) => {
      addToast(`Failed to ${vars.action} card #${vars.cardId}`, 'error')
    },
  })
}
```

**Step 2: Create InlineConfirm component**

Create `dashboard/frontend/src/features/inbox/InlineConfirm.tsx`:

```typescript
import { useState } from 'react'

interface InlineConfirmProps {
  label: string
  onConfirm: (rationale: string) => void
  showRationale?: boolean
  disabled?: boolean
}

export function InlineConfirm({ label, onConfirm, showRationale = true, disabled }: InlineConfirmProps) {
  const [confirming, setConfirming] = useState(false)
  const [rationale, setRationale] = useState('')

  if (!confirming) {
    return (
      <button onClick={() => setConfirming(true)} disabled={disabled}>
        {label}
      </button>
    )
  }

  return (
    <span style={{ display: 'inline-flex', gap: '4px', alignItems: 'center' }}>
      {showRationale && (
        <input
          type="text"
          placeholder="reason (optional)"
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          style={{ fontSize: '0.75rem', width: '120px' }}
        />
      )}
      <button onClick={() => { onConfirm(rationale); setConfirming(false); setRationale('') }}>
        Confirm
      </button>
      <button onClick={() => { setConfirming(false); setRationale('') }}>
        Cancel
      </button>
    </span>
  )
}
```

**Step 3: Create ActionTray**

Create `dashboard/frontend/src/features/inbox/ActionTray.tsx`:

```typescript
import type { Card } from '../../api/types'
import { useCardDecision } from '../../hooks/useCardDecision'
import { InlineConfirm } from './InlineConfirm'
import { openSession } from '../../api/client'
import { useToastStore } from '../../stores/toast'
import styles from './ActionTray.module.css'

interface ActionTrayProps {
  card: Card
  onApprove: () => void
}

export function ActionTray({ card, onApprove }: ActionTrayProps) {
  const decision = useCardDecision()
  const addToast = useToastStore((s) => s.addToast)

  const handleHold = (rationale: string) => {
    decision.mutate({
      cardId: card.id,
      action: 'hold',
      decision: 'rejected',
      rationale,
      followUp: { endpoint: 'hold' },
    })
  }

  const handleClose = (rationale: string) => {
    decision.mutate({
      cardId: card.id,
      action: 'close',
      decision: 'approved',
      rationale,
      followUp: { endpoint: 'close', body: { note: rationale } },
    })
  }

  const handleJira = (rationale: string) => {
    decision.mutate({
      cardId: card.id,
      action: 'write-jira',
      decision: 'approved',
      rationale,
      followUp: { endpoint: 'write-jira', body: { note: rationale } },
    })
  }

  const handleDailyLog = (rationale: string) => {
    decision.mutate({
      cardId: card.id,
      action: 'daily-log',
      decision: 'approved',
      rationale,
      followUp: { endpoint: 'daily-log', body: { note: rationale } },
    })
  }

  const handleSendDraft = (channel: 'send-slack' | 'send-email') => {
    decision.mutate({
      cardId: card.id,
      action: channel,
      decision: 'approved',
      followUp: { endpoint: channel },
    })
  }

  const handleOpenSession = async () => {
    try {
      await openSession('cards', card.id)
      addToast(`Session opened for card #${card.id}`, 'success')
    } catch {
      addToast(`Failed to open session for card #${card.id}`, 'error')
    }
  }

  return (
    <div className={styles.tray}>
      <button onClick={onApprove}>Approve</button>
      <InlineConfirm label="Hold" onConfirm={handleHold} />
      <InlineConfirm label="Close" onConfirm={handleClose} />
      <InlineConfirm label="Jira" onConfirm={handleJira} />
      <InlineConfirm label="Daily Log" onConfirm={handleDailyLog} showRationale={false} />
      {card.source === 'slack' && card.draft_response && (
        <button onClick={() => handleSendDraft('send-slack')}>Send Draft</button>
      )}
      {card.source === 'gmail' && card.draft_response && (
        <button onClick={() => handleSendDraft('send-email')}>Send Draft</button>
      )}
      <button onClick={handleOpenSession}>Open Session</button>
    </div>
  )
}
```

**Step 4: Wire ActionTray into CardItem**

Modify `CardItem.tsx` to render ActionTray when the card is selected/expanded.

**Step 5: Build and verify**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run build
```

**Step 6: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add ActionTray with decision flow, InlineConfirm, and useCardDecision hook"
```

---

### Task 9: WebSocket Terminal component

**Files:**
- Create: `dashboard/frontend/src/features/terminal/Terminal.tsx`
- Create: `dashboard/frontend/src/features/terminal/Terminal.module.css`
- Modify: `dashboard/frontend/src/features/inbox/CardItem.tsx`

**Step 1: Create Terminal component**

Create `dashboard/frontend/src/features/terminal/Terminal.tsx`:

```typescript
import { useEffect, useRef } from 'react'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from '@xterm/addon-fit'
import 'xterm/css/xterm.css'
import styles from './Terminal.module.css'

interface TerminalProps {
  cardId: number
  decisionEventId: number
  onClose: () => void
}

export function Terminal({ cardId, decisionEventId, onClose }: TerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<XTerm | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const term = new XTerm({
      theme: { background: '#000000', foreground: '#ffffff', cursor: '#ffffff' },
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: 13,
      scrollback: 5000,
      cursorBlink: true,
    })
    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(containerRef.current)
    fitAddon.fit()
    termRef.current = term

    // WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/execute/${cardId}?decision_event_id=${decisionEventId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (e) => term.write(e.data)
    ws.onclose = () => onClose()
    ws.onerror = () => onClose()

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data)
    })

    // Resize observer
    const observer = new ResizeObserver(() => fitAddon.fit())
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      ws.close()
      term.dispose()
    }
  }, [cardId, decisionEventId, onClose])

  return <div ref={containerRef} className={styles.container} />
}
```

Create `dashboard/frontend/src/features/terminal/Terminal.module.css`:

```css
.container {
  width: 100%;
  min-height: 300px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm, 0);
  overflow: hidden;
  margin-top: 0.5rem;
}
```

**Step 2: Wire Terminal into CardItem on approve**

Update `CardItem.tsx` to track `running` state. When user clicks Approve in ActionTray, the card enters running state, shows the Terminal component, hides the ActionTray.

**Step 3: Add xterm CSS import to vite config if needed**

The `import 'xterm/css/xterm.css'` in Terminal.tsx should work with Vite's CSS handling. Verify the build includes it.

**Step 4: Build and verify**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run build
```

**Step 5: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add xterm.js WebSocket Terminal component for card execution"
```

---

### Task 10: RefineChat component

**Files:**
- Create: `dashboard/frontend/src/features/refine/RefineChat.tsx`
- Create: `dashboard/frontend/src/features/refine/RefineChat.module.css`

**Step 1: Create RefineChat**

Create `dashboard/frontend/src/features/refine/RefineChat.tsx`:

```typescript
import { useState, useEffect, useRef } from 'react'
import { fetchChatHistory, postRefine } from '../../api/client'
import type { ChatMessage } from '../../api/types'
import styles from './RefineChat.module.css'

interface RefineChatProps {
  entityType: 'cards' | 'tasks'
  entityId: number
}

export function RefineChat({ entityType, entityId }: RefineChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (loaded) return
    fetchChatHistory(entityType, entityId)
      .then((res) => { setMessages(res.messages); setLoaded(true) })
      .catch(() => setLoaded(true))
  }, [entityType, entityId, loaded])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    const userMsg: ChatMessage = { id: Date.now(), role: 'user', content: text, created_at: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }))
      const res = await postRefine(entityType, entityId, text, history)
      const assistantMsg: ChatMessage = { id: Date.now() + 1, role: 'assistant', content: res.response, created_at: new Date().toISOString() }
      setMessages((prev) => [...prev, assistantMsg])
    } catch {
      const errMsg: ChatMessage = { id: Date.now() + 1, role: 'assistant', content: 'Error: could not refine', created_at: new Date().toISOString() }
      setMessages((prev) => [...prev, errMsg])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className={styles.chat}>
      <div className={styles.history}>
        {messages.map((m) => (
          <div key={m.id} className={`${styles.message} ${styles[m.role]}`}>
            <span className={styles.label}>{m.role === 'user' ? 'YOU' : 'BUDDY'}</span>
            <span>{m.content}</span>
          </div>
        ))}
        {loading && <div className={styles.message}><span className={styles.label}>BUDDY</span> thinking...</div>}
      </div>
      <div className={styles.inputArea}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Refine this card..."
          rows={2}
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()}>Send</button>
      </div>
    </div>
  )
}
```

Create appropriate CSS module for styling.

**Step 2: Commit**

```bash
git add dashboard/frontend/src/features/refine/
git commit -m "Add RefineChat component for card and task refinement"
```

---

### Task 11: Toast component

**Files:**
- Create: `dashboard/frontend/src/components/ToastContainer.tsx`
- Create: `dashboard/frontend/src/components/ToastContainer.module.css`
- Modify: `dashboard/frontend/src/layouts/AppLayout.tsx`

**Step 1: Create ToastContainer**

Create `dashboard/frontend/src/components/ToastContainer.tsx`:

```typescript
import { useToastStore } from '../stores/toast'
import styles from './ToastContainer.module.css'

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)
  const removeToast = useToastStore((s) => s.removeToast)

  if (toasts.length === 0) return null

  return (
    <div className={styles.container}>
      {toasts.map((t) => (
        <div key={t.id} className={`${styles.toast} ${styles[t.level]}`}>
          <span>{t.message}</span>
          <button onClick={() => removeToast(t.id)} className={styles.close}>&times;</button>
        </div>
      ))}
    </div>
  )
}
```

Create `dashboard/frontend/src/components/ToastContainer.module.css`:

```css
.container {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  display: flex;
  flex-direction: column-reverse;
  gap: 0.5rem;
  z-index: 10000;
  max-width: 360px;
}

.toast {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-sm, 8px);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  animation: slideIn 0.2s ease-out;
  border: 1px solid var(--border-subtle);
  background: var(--surface, #1a1a1a);
  color: var(--text, #fff);
}

.success { border-left: 3px solid var(--fresh); }
.error { border-left: 3px solid var(--gmail); }
.info { border-left: 3px solid var(--jira); }

.close {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 1.1rem;
  margin-left: auto;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
```

**Step 2: Add ToastContainer to AppLayout**

Add `<ToastContainer />` at the bottom of `AppLayout.tsx`.

**Step 3: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add ToastContainer component with auto-dismiss and level styling"
```

---

### Task 12: Debug drawer

**Files:**
- Create: `dashboard/frontend/src/features/debug/DebugDrawer.tsx`
- Create: `dashboard/frontend/src/features/debug/DebugDrawer.module.css`
- Modify: `dashboard/frontend/src/layouts/AppLayout.tsx`

**Step 1: Create DebugDrawer**

Create `dashboard/frontend/src/features/debug/DebugDrawer.tsx`:

```typescript
import { useDebugStore } from '../../stores/debug'
import { sendDebugToClaude } from '../../api/client'
import { useToastStore } from '../../stores/toast'
import styles from './DebugDrawer.module.css'

export function DebugDrawer() {
  const { entries, isOpen, toggle, clear, markSent } = useDebugStore()
  const addToast = useToastStore((s) => s.addToast)

  const handleSendToClaude = async (entry: typeof entries[0]) => {
    try {
      await sendDebugToClaude(entry.message, entry.level, 'REACT', entry.details)
      markSent(entry.id)
      addToast('Sent to Claude', 'success')
    } catch {
      addToast('Failed to send to Claude', 'error')
    }
  }

  return (
    <>
      <button className={styles.toggle} onClick={toggle}>
        {isOpen ? 'CLOSE DEBUG' : `DEBUG (${entries.length})`}
      </button>
      {isOpen && (
        <div className={styles.drawer}>
          <div className={styles.header}>
            <span>Debug Log ({entries.length})</span>
            <button onClick={clear}>Clear All</button>
          </div>
          <div className={styles.entries}>
            {entries.map((e) => (
              <div key={e.id} className={`${styles.entry} ${styles[e.level]}`}>
                <span className={styles.badge}>{e.level.toUpperCase()}</span>
                <span className={styles.message}>{e.message}</span>
                <span className={styles.time}>{new Date(e.timestamp).toLocaleTimeString()}</span>
                {e.level === 'error' && !e.sentToClaude && (
                  <button onClick={() => handleSendToClaude(e)} className={styles.sendBtn}>
                    Send to Claude
                  </button>
                )}
                {e.sentToClaude && <span className={styles.sent}>sent</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
```

Create appropriate CSS module. Wire into AppLayout.

**Step 2: Add global error handlers in AppLayout**

In `AppLayout.tsx`, add a `useEffect` that registers `window.onerror` and `window.onunhandledrejection` handlers, logging to `useDebugStore.addEntry`.

**Step 3: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add DebugDrawer with send-to-Claude and global error capture"
```

---

### Task 13: Gmail-specific actions

**Files:**
- Create: `dashboard/frontend/src/features/inbox/GmailActions.tsx`
- Modify: `dashboard/frontend/src/features/inbox/ActionTray.tsx`

**Step 1: Create GmailActions component**

Create `dashboard/frontend/src/features/inbox/GmailActions.tsx` with buttons for: Suggest Labels, Auto Label, Suggest Draft, Archive. Each calls the appropriate API (`gmailAnalyze`, `performCardAction` with `gmail-auto-label`, `archive-email`). Uses the decision flow for auto-label and archive.

**Step 2: Wire into ActionTray for gmail source cards**

**Step 3: Commit**

```bash
git add dashboard/frontend/src/features/inbox/
git commit -m "Add Gmail-specific actions: suggest labels, auto label, suggest draft, archive"
```

---

### Task 14: TasksView

**Files:**
- Create: `dashboard/frontend/src/features/tasks/TasksView.tsx`
- Create: `dashboard/frontend/src/features/tasks/TasksView.module.css`
- Create: `dashboard/frontend/src/features/tasks/TaskCard.tsx`
- Modify: `dashboard/frontend/src/router.tsx`

**Step 1: Create TasksView**

Fetch tasks via `useQuery(['tasks'], fetchTasks)`. Filter out completed/closed/done/cancelled. Render each as a `TaskCard` with: title, status badge, priority, description, action buttons (close, write-jira, daily-log, open-session, refine toggle). Uses the same decision flow as cards but with `entityType: 'tasks'`.

**Step 2: Create TaskCard with actions**

Task-specific decision hook: `postDecision('tasks', taskNumber, ...)`. Refine chat with `entityType: 'tasks'`.

**Step 3: Wire into router**

Replace placeholder in `router.tsx`:
```typescript
import { TasksView } from './features/tasks/TasksView'
// ...
{ path: 'tasks', element: <TasksView /> },
```

**Step 4: Build and test**

**Step 5: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add TasksView with task cards, actions, and refine chat"
```

---

### Task 15: JiraSprintView

**Files:**
- Create: `dashboard/frontend/src/features/jira/JiraSprintView.tsx`
- Create: `dashboard/frontend/src/features/jira/JiraSprintView.module.css`
- Modify: `dashboard/frontend/src/router.tsx`

**Step 1: Create JiraSprintView**

Fetch sprint via `useQuery(['jira-sprint'], () => fetchJiraSprint())` and Jira cards via `useQuery(['cards', 'jira'], () => fetchCards('jira'))`. Merge issues with linked cards. Group by status columns (TODO, IN PROGRESS, DONE). Show a refresh button that calls `fetchJiraSprint(true)`. Each issue shows key, summary, status, assignee. Linked cards show action buttons.

**Step 2: Wire into router, build, commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add JiraSprintView with sprint issues, status columns, and card linking"
```

---

### Task 16: CalendarView

**Files:**
- Create: `dashboard/frontend/src/features/calendar/CalendarView.tsx`
- Create: `dashboard/frontend/src/features/calendar/CalendarView.module.css`
- Modify: `dashboard/frontend/src/router.tsx`

**Step 1: Create CalendarView**

Fetch calendar cards via `useQuery(['cards', 'calendar'], () => fetchCards('calendar'))`. Parse events from `proposed_actions`. Group by: TODAY'S AGENDA, UPCOMING THIS WEEK, NEXT WEEK based on timestamp comparison. Each event shows time, title, optional join link (button if `hangout_link` exists), prep notes button (calls `openSession`).

**Step 2: Wire into router, build, commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add CalendarView with event grouping, join links, and prep notes"
```

---

### Task 17: DailyLogView and LearningsView

**Files:**
- Create: `dashboard/frontend/src/features/daily/DailyLogView.tsx`
- Create: `dashboard/frontend/src/features/learnings/LearningsView.tsx`
- Modify: `dashboard/frontend/src/router.tsx`

**Step 1: Create DailyLogView**

Fetch date list via `useQuery(['daily-logs'], fetchDailyLogs)`. Date selector component (dropdown or date input). Selected date fetches content via `useQuery(['daily-log', date], () => fetchDailyLog(date))`. Renders pre/post stats if available, raw log content in a `<pre>` block.

**Step 2: Create LearningsView**

Day/week toggle + date picker. Fetches summary via `useQuery(['learnings-summary', range, date], () => fetchLearningsSummary(range, date))` and events via `useQuery(['learnings-events', range, date], () => fetchLearningsEvents(range, date))`. Renders buckets, pending categories, top titles, recent events list.

**Step 3: Wire into router, build, commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add DailyLogView and LearningsView with date selection and content display"
```

---

### Task 18: KnowledgeView and SuggestionsView

**Files:**
- Create: `dashboard/frontend/src/features/knowledge/KnowledgeView.tsx`
- Create: `dashboard/frontend/src/features/suggestions/SuggestionsView.tsx`
- Modify: `dashboard/frontend/src/router.tsx`

**Step 1: Create KnowledgeView**

Fetch doc list via `useQuery(['knowledge-index'], fetchKnowledgeIndex)`. Client-side search filter on path/group/name. Split pane: left shows filtered doc list, right shows selected doc content fetched via `useQuery(['knowledge-doc', path], () => fetchKnowledgeDoc(path), { enabled: !!path })`.

**Step 2: Create SuggestionsView**

Fetch via `useQuery(['suggestions'], () => fetchSuggestions())`. Two sections: active (pending) and held (collapsed by default). Each suggestion card has approve/deny buttons. Approve calls `performCardAction(id, 'approve')`. Deny calls `performCardAction(id, 'deny')`. Refresh button triggers `fetchSuggestions(true)`.

**Step 3: Wire into router, build, commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add KnowledgeView with search and doc viewer, SuggestionsView with approve/deny"
```

---

### Task 19: PlaybooksView

**Files:**
- Create: `dashboard/frontend/src/features/playbooks/PlaybooksView.tsx`
- Create: `dashboard/frontend/src/features/playbooks/PlaybooksView.module.css`
- Modify: `dashboard/frontend/src/router.tsx`

**Step 1: Create PlaybooksView**

Fetch drafts via `useQuery(['playbook-drafts'], fetchPlaybookDrafts)` and approved via `useQuery(['playbooks'], fetchPlaybooks)`. Drafts section shows each with steps, confidence, approve/reject buttons. Approved section shows each with steps, execution count, execution button with approval text input. Execute calls `executePlaybook(id, context, approvalText)`.

**Step 2: Wire into router, build, commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add PlaybooksView with draft review and execution dispatch"
```

---

### Task 20: BriefingModal

**Files:**
- Create: `dashboard/frontend/src/features/briefing/BriefingModal.tsx`
- Create: `dashboard/frontend/src/features/briefing/BriefingModal.module.css`
- Modify: `dashboard/frontend/src/layouts/AppLayout.tsx`

**Step 1: Create BriefingModal**

Component with `open` boolean state. Trigger: button in header or keyboard shortcut. Fetches `useQuery(['briefing'], fetchBriefing, { enabled: open })`. Renders modal overlay with: cognitive load level (color-coded), meetings with times, items needing response, alerts, stats, pep talk. Dismiss on click-outside or close button.

**Step 2: Add briefing button to Header, wire modal into AppLayout**

**Step 3: Commit**

```bash
git add dashboard/frontend/src/
git commit -m "Add BriefingModal with cognitive load display and meeting prep"
```

---

### Task 21: Build, deploy, retire vanilla JS

**Files:**
- Modify: `dashboard/server.py` (root route)
- Modify: `dashboard/frontend/vite.config.ts` (if needed)

**Step 1: Build production React app**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npm run build
```

Expected: Output in `dashboard/static-react/`

**Step 2: Run full test suite**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy/dashboard/frontend
npx vitest run
```

Expected: All tests pass

**Step 3: Update server.py root route**

Change the `/` route to always serve React (remove vanilla JS fallback):

```python
@app.get("/")
async def root():
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/app", status_code=302)
```

**Step 4: Run dashboard server tests**

```bash
cd /Users/kioja.kudumu/.claude/skills/eng-buddy
python3 -m pytest dashboard/tests/test_server.py -v
```

Expected: All pass (44/44)

**Step 5: Commit**

```bash
git add dashboard/frontend/ dashboard/server.py dashboard/static-react/
git commit -m "Complete React dashboard Wave 2: full vanilla JS parity, retire vanilla fallback"
```

**Step 6: Push**

```bash
git push origin main
```
