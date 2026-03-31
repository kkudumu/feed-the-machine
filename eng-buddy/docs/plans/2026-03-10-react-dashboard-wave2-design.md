# React Dashboard Wave 2 Design — Full Vanilla JS Parity

**Goal:** Port every remaining vanilla JS feature to React, making the React app the sole dashboard. After this wave, `static/index.html` and `static/app.js` are retired.

**Depends on:** Wave 1 (card inbox core loop — complete)

**Tech additions:** React Router v6, xterm.js (npm), @tanstack/react-query-devtools

---

## Architecture

### Routing (React Router v6)

```
/app                  → redirect to /app/inbox
/app/inbox            → CardInbox (Wave 1 enhanced with actions)
/app/inbox/:source    → CardInbox filtered (slack, gmail, jira, freshservice, calendar)
/app/tasks            → TasksView
/app/jira             → JiraSprintView
/app/calendar         → CalendarView
/app/daily            → DailyLogView
/app/learnings        → LearningsView
/app/knowledge        → KnowledgeView
/app/suggestions      → SuggestionsView
/app/playbooks        → PlaybooksView
```

Layout shell: persistent `<Header>` + `<Sidebar>` wrapping `<Outlet />`. Sidebar links become `<NavLink>` with active styling.

### State Architecture

| Layer | Responsibility |
|-------|---------------|
| **Zustand** (`useUIStore`) | Theme, mode, terminal selection, active card |
| **Zustand** (`useDebugStore`) | Debug drawer entries |
| **Zustand** (`useToastStore`) | Toast notification stack |
| **TanStack Query** | All server data (cards, tasks, pollers, settings, plans, etc.) |
| **React Router** | Tab/view navigation, URL state |
| **Component-local** | WebSocket instances, terminal refs, refine chat history |

### Theme System

6 CSS variable sets (3 themes × 2 modes) defined in `themes.css`. Each set overrides the same custom properties (`--bg-deep`, `--bg-surface`, `--accent-pink`, etc.). Applied via `data-theme` and `data-mode` attributes on `<html>`.

Themes:
- Midnight Ops (dark/light)
- Soft Kitty (dark/light)
- Neon Dreams (dark/light) — default

Existing `tokens.css` becomes the Neon Dreams dark defaults. The 6 vanilla CSS theme files are converted to variable-only definitions. Switching is instant — no `<link>` tag swap, no flash.

Persistence: `POST /api/settings` + localStorage fallback for instant application before API response.

---

## Header Controls

### Theme Picker
- `<select>` with 3 theme options
- On change: update `useUIStore.theme`, set `data-theme` on `<html>`, persist via settings API + localStorage

### Mode Toggle
- Button with moon/sun icon
- Toggles `useUIStore.mode` between dark/light
- Sets `data-mode` on `<html>`, persist to settings API + localStorage

### Terminal Picker
- `<select>` with 5 options: Terminal, Warp, iTerm, Alacritty, kitty
- Persists via settings API
- Value used when opening execution sessions (`POST /api/cards/{id}/open-session`)

### Restart Button
- Button with phase-aware text
- Click: `POST /api/restart` → poll `/api/health` every 500ms → poll `/api/restart-status` for phases (restarting → syncing → complete)
- 2-minute timeout
- Disabled + text changes during restart cycle

### Poller Timers
- `useQuery(['pollers'])` fetches `GET /api/pollers/status` every 30s
- `usePollerCountdown` hook: 1-second `setInterval` decrements displayed countdowns between API fetches
- Each badge clickable: `POST /api/pollers/{id}/sync` triggers immediate sync
- Badge colors: syncing, healthy, warning, error

### macOS Notifications Toggle
- Checkbox in header settings area
- Stored via settings API
- When enabled + SSE delivers new card → `POST /api/notify`

### Settings Initialization
- `useQuery(['settings'])` fetches `GET /api/settings` on mount
- Hydrates Zustand store (theme, mode, terminal, notifications)
- localStorage provides instant theme before API responds

---

## Card Actions & Status Transitions

### Action Tray

Expands on card selection. Actions vary by source and status:

**Universal actions** (all cards):
- Approve/Execute → decision API + WebSocket terminal
- Hold → decision API (rejected) + hold API
- Close → decision API + close API
- Write to Jira → write-jira API
- Daily Log → daily-log API
- Refine → toggles inline chat panel
- Open Session → open-session API

**Source-specific actions:**
- Slack: Send Draft (`send-slack`)
- Gmail: Send Draft (`send-email`), Suggest Labels (`gmail-analyze`), Auto Label (`gmail-auto-label`), Suggest Draft (`gmail-analyze`), Archive (`archive-email`)
- Suggestions: Approve/Deny (separate endpoints)

### Decision Flow

Every destructive action flows through `useCardDecision` mutation hook:
1. `POST /api/cards/{id}/decision` with action, decision, rationale
2. Receives `decision_event_id`
3. Passes ID to the action endpoint

Preserves full audit trail.

### Confirmation UX

No `window.confirm`/`window.prompt`. Instead: inline confirmation component — button text changes to "Confirm?" with optional rationale text input, second click executes.

### Status Transitions

Visual state via CSS classes:
- `pending` — default card style
- `held` — muted/dimmed with held badge
- `running` — pulsing glow border, terminal visible inline
- `completed` — success badge, fade to 0.5 opacity

---

## WebSocket Terminal

### `<Terminal />` Component

- `useRef` for DOM container
- `useEffect` initializes xterm.js `Terminal` instance + fit addon
- Props: `cardId`, `decisionEventId`, `onClose`

### Connection

- WebSocket URL: `ws(s)://{host}/ws/execute/{cardId}?decision_event_id={uuid}`
- Bidirectional: `ws.onmessage` → `term.write()`, `term.onData()` → `ws.send()`
- On WebSocket close: `onClose` callback fires, card transitions to `completed`

### Config

Matches vanilla JS:
- Font: JetBrains Mono, 13px
- Scrollback: 5000 lines
- Dark theme (black bg, white text)

### Integration

When user approves a card, action tray collapses, `<Terminal />` renders inline below card summary. Card status → `running`. Terminal stays until WebSocket closes.

### Resize

`ResizeObserver` on terminal container triggers `fitAddon.fit()`.

### State

Terminal instances tracked per-card in component-local Map (not Zustand — ephemeral).

---

## Tab Views

Each tab is a route component using TanStack Query for data.

### Inbox (`/app/inbox/:source?`)
Existing Wave 1 CardList enhanced with action tray. Gmail/Slack use two-section layout (needs action / no action) via `fetchInboxView`. Gmail view also shows filter suggestions from `GET /api/filters/suggestions`. Other sources use `fetchCards`.

### Tasks (`/app/tasks`)
`GET /api/tasks`, filters out completed. Task cards with: refine chat, close, write-jira, daily-log, open-session. Same decision flow as cards. Task-specific endpoints: `/api/tasks/{number}/decision`, `/api/tasks/{number}/refine`, etc.

### Jira (`/app/jira`)
`GET /api/jira/sprint` + `GET /api/cards?source=jira&status=all`. Merges sprint issues with dashboard cards. Groups by status columns (TODO, IN PROGRESS, DONE). Fallback render for unsynced issues. Optional refresh param.

### Calendar (`/app/calendar`)
`GET /api/cards?source=calendar`. Groups events by: TODAY'S AGENDA, UPCOMING THIS WEEK, NEXT WEEK. Each event shows time, join link (if hangout_link), prep notes button (opens session).

### Daily (`/app/daily`)
`GET /api/daily/logs` for date list. `GET /api/daily/logs/{date}` for content + stats. Date selector component, pre/post stats display, raw log content renderer.

### Learnings (`/app/learnings`)
`GET /api/learnings/summary?range={day|week}&date=YYYY-MM-DD` + `GET /api/learnings/events`. Day/week toggle, date picker. Renders buckets, pending categories, top titles, recent events.

### Knowledge (`/app/knowledge`)
`GET /api/knowledge/index` for doc list. `GET /api/knowledge/doc?path=...` for content. Client-side search filter on path/group/name. Split pane: list on left, content viewer on right.

### Suggestions (`/app/suggestions`)
`GET /api/suggestions`. Active and held sections (held collapsed by default). Approve/deny actions with decision flow. Refresh button triggers `?refresh=true`.

### Playbooks (`/app/playbooks`)
`GET /api/playbooks` + `GET /api/playbooks/drafts`. Draft review with approve/reject buttons. Approved playbooks show execution button with approval text input. `POST /api/playbooks/execute` dispatches execution.

---

## Refine Chat

Inline collapsible component, used by both cards and tasks.

- First toggle: `GET /api/{cards|tasks}/{id}/chat-history` loads history
- Messages rendered as user/assistant bubbles
- Input: textarea, Shift+Enter = newline, Enter = send
- `POST /api/{cards|tasks}/{id}/refine` with `{ message, history }`
- Response appended immediately, input cleared

---

## Toast System

`useToastStore` (Zustand):
- `addToast(message, level)` where level = `success | error | info`
- Fixed-position stack, bottom-right
- Auto-dismiss after 4 seconds
- Replaces all `window.alert`/`window.confirm` from vanilla JS

Used for: action confirmations, API errors, send confirmations, execution status changes.

---

## Debug Drawer

`useDebugStore` (Zustand) stores entries (max 150).

### Instrumented Fetch
Custom `useInstrumentedFetch` hook wraps all API calls. Logs: method, URL, status code, duration (ms), response summary.

### Error Capture
Global handlers: `window.onerror` and `unhandledrejection` log to debug store.

### UI
- Slide-up drawer from bottom of screen
- Toggle button in header
- Each entry: level badge (info/warn/error), message, timestamp
- "Send to Claude" button per error → `POST /api/debug/send-to-claude`
- "Clear All" button
- TanStack Query DevTools available in dev mode

---

## Briefing Modal

- Trigger: header button or keyboard shortcut
- `GET /api/briefing` fetches data (cached on server)
- Modal overlay renders:
  - Cognitive load level with color coding
  - Meetings with times and prep notes
  - Items needing response with draft status
  - Alerts (urgent/informational)
  - Stats (drafts sent, triaged, time saved)
  - Pep talk
- Dismiss via click-outside or close button

---

## Migration Completion

After Wave 2:
1. `/` route changes from redirect-to-React to serving React directly (no more vanilla JS fallback)
2. `static/app.js` and `static/index.html` can be archived/removed
3. `static/themes/*.css` replaced by `themes.css` variable definitions
4. React app is the sole dashboard interface

---

## File Structure (New/Modified)

```
dashboard/frontend/src/
├── router.tsx                          # React Router config
├── layouts/
│   └── AppLayout.tsx                   # Header + Sidebar + Outlet
├── features/
│   ├── inbox/                          # Enhanced with actions
│   │   ├── ActionTray.tsx
│   │   ├── InlineConfirm.tsx
│   │   └── GmailActions.tsx
│   ├── terminal/
│   │   └── Terminal.tsx                # xterm.js wrapper
│   ├── refine/
│   │   └── RefineChat.tsx
│   ├── tasks/
│   │   └── TasksView.tsx
│   ├── jira/
│   │   └── JiraSprintView.tsx
│   ├── calendar/
│   │   └── CalendarView.tsx
│   ├── daily/
│   │   └── DailyLogView.tsx
│   ├── learnings/
│   │   └── LearningsView.tsx
│   ├── knowledge/
│   │   └── KnowledgeView.tsx
│   ├── suggestions/
│   │   └── SuggestionsView.tsx
│   ├── playbooks/
│   │   └── PlaybooksView.tsx
│   ├── briefing/
│   │   └── BriefingModal.tsx
│   ├── debug/
│   │   └── DebugDrawer.tsx
│   └── header/
│       ├── ThemePicker.tsx
│       ├── ModeToggle.tsx
│       ├── TerminalPicker.tsx
│       ├── RestartButton.tsx
│       ├── PollerTimers.tsx
│       └── NotificationToggle.tsx
├── stores/
│   ├── ui.ts                           # Extended with theme/mode/terminal
│   ├── debug.ts
│   └── toast.ts
├── hooks/
│   ├── useSettings.ts                  # GET/POST /api/settings
│   ├── usePollerCountdown.ts
│   ├── useCardDecision.ts
│   ├── useInstrumentedFetch.ts
│   └── useWebSocket.ts
├── theme/
│   ├── tokens.css                      # Existing (becomes neon-dreams dark default)
│   └── themes.css                      # 6 variable sets (3 themes × 2 modes)
└── api/
    ├── types.ts                        # Extended with all missing types
    └── client.ts                       # Extended with all missing endpoints
```
