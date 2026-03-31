# React Dashboard Wave 4: Theme Plumbing + Playbook Management

**Date:** 2026-03-11
**Scope:** Wire up broken theme hydration; enhance PlaybooksView with draft editing, promote/delete, execution history

## Part 1: Theme Plumbing Fix

### Problem
ThemePicker and ModeToggle exist in the header but settings don't hydrate on app load. Refreshing loses theme state because `<html>` `data-theme`/`data-mode` attributes aren't set from persisted settings.

### Fix (3 touchpoints, no new components or endpoints)

1. **`stores/ui.ts`** — Add `theme` and `mode` state fields + `hydrateSettings()` action
   - Fetches `GET /api/settings`
   - Sets Zustand state (`theme`, `mode`, `terminal`, `macosNotifications`)
   - Sets `document.documentElement.dataset.theme` and `dataset.mode`

2. **`AppLayout.tsx`** — Call `hydrateSettings()` on mount before first render

3. **`ThemePicker.tsx` / `ModeToggle.tsx`** — After `POST /api/settings` mutation, immediately set `document.documentElement.dataset` attrs (don't wait for re-fetch)

### Files
- `src/stores/ui.ts` — extend with theme/mode state + hydration
- `src/layouts/AppLayout.tsx` — add hydration call on mount
- `src/features/header/ThemePicker.tsx` — sync DOM attrs on change
- `src/features/header/ModeToggle.tsx` — sync DOM attrs on change
- `src/api/types.ts` — add `SettingsResponse` interface

## Part 2: Playbook Management

### A. Draft Review & Edit UI
Enhance existing `PlaybooksView.tsx` with exftmble draft detail view:
- Expand a draft → step table (step name, MCP tool, risk level)
- Inline edit: tweak step params, reorder steps, delete a step
- No blank-canvas creation — drafts come from the playbook engine
- New endpoint: `PATCH /api/playbooks/drafts/{id}` to persist edits

### B. Promote / Delete Actions
Wire existing endpoints to UI with proper UX:
- Promote button → `POST /api/playbooks/{id}/promote` → toast + move to published list
- Delete button → inline confirm → `DELETE /api/playbooks/drafts/{id}` → remove from list

### C. Execution History
- New endpoint: `GET /api/playbooks/{id}/history` — past runs with timestamps, step outcomes, pass/fail
- Exftmble run rows showing per-step results
- Status badges: success / failed / partial

### Files
- `src/features/playbooks/PlaybooksView.tsx` — extend with tabbed layout (drafts/published/history)
- `src/features/playbooks/DraftEditor.tsx` — new: exftmble draft with step table + inline edit
- `src/features/playbooks/RunHistory.tsx` — new: execution history list
- `src/features/playbooks/RunDetail.tsx` — new: exftmble per-step run results
- `src/api/client.ts` — add playbook edit, history API functions
- `src/api/types.ts` — add playbook edit/history types
- `dashboard/server.py` — add `PATCH /api/playbooks/drafts/{id}`, `GET /api/playbooks/{id}/history`

## Non-Goals
- No audit log (debug drawer covers it)
- No dedicated Settings tab/page
- No blank-canvas playbook authoring (engine generates drafts)
