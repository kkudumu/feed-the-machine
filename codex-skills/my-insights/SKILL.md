---
name: my-insights
description: Generate rich HTML insights reports from Codex session data. Use when user says "my-insights", "insights", "usage report", "session report", "analyze my sessions". Supports flexible date ranges.
---

## Codex Native Baseline

These copies target Codex, not Claude. If any later section uses legacy wording, follow these Codex-native rules first:

- Ask user questions directly in chat while running in Default mode. Only use `request_user_input` if the session is actually in Plan mode.
- Prefer local tool work and `multi_tool_use.parallel` for parallelism. Use `spawn_agent` only when the user explicitly asks for sub-agents, delegation, or parallel agent work.
- Open `references/*.md` files when needed; they are not auto-loaded automatically.
- Do not rely on `TaskCreate`, `TaskList`, Claude command files, or `claude -p`.
- Treat any remaining external-model or external-CLI workflow as legacy reference unless this skill includes a Codex-native override below.

## Codex Native Overrides

- The aggregate/report workflow is the native path. If the bundled facet-generation helpers still depend on a legacy CLI adapter, continue with cached facets or aggregate-only reporting instead of blocking the whole skill.
- Keep the skill useful even without LLM facet generation: parse the date range, read sessions, aggregate them, render the report, and tell the user what enrichment was skipped.


# My Insights

Generate a personalized HTML insights report from your Codex session data — like `/insights` but with no session cap, full date range support, and processing of all real interactive sessions.

## Usage

`$my-insights` — analyze all available sessions
`$my-insights jan march` — analyze January through March
`$my-insights 2026-02-01 2026-03-31` — specific date range
`$my-insights last 90 days` — relative range

## Pipeline

Run these steps sequentially, reporting progress at each stage.

### Step 1: Parse Date Range

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.codex/skills/my-insights/scripts'))
from date_parser import parse_date_range

# Parse the user's args (everything after $my-insights)
start_date, end_date = parse_date_range(args)
```

Report: "Analyzing sessions from {start_date} to {end_date}"

### Step 2: Read & Filter Sessions

```python
from session_reader import read_sessions

result = read_sessions(start_date, end_date)
sessions = result["sessions"]
stats = result["stats"]
```

Report: "Found {stats.total_found} sessions in range, {stats.filtered_interactive} interactive (excluded {stats.excluded_automated} automated, {stats.excluded_short} ultra-short)"

If sessions is empty, stop and report: "No interactive sessions found in {start_date} to {end_date}."

### Step 3: Generate Facets

This is the longest step. For each session without a cached facet, run the bundled facet generator if it works in your local Codex setup; otherwise skip enrichment and continue with the cached or aggregate-only path.

```python
from facet_generator import generate_facets

result = generate_facets(sessions, on_progress=lambda gen, total, wave, waves:
    print(f"[{gen}/{total}] Wave {wave}/{waves}"))
facets = result["facets"]
```

Report progress during generation. After: "Facets: {result.generated} generated, {result.cached} cached, {result.failed} failed"

**Parallel optimization**: If there are >50 sessions needing facets, split the uncached sessions into chunks and dispatch multiple agents to run `generate_facets()` in parallel. Each agent handles a chunk. Merge results afterward.

### Step 4: Aggregate

```python
from aggregator import aggregate

aggregated = aggregate(sessions, facets)
```

Report: "Aggregated {aggregated.total_sessions} sessions: {aggregated.total_messages} messages, {aggregated.active_days} active days"

### Step 5: Generate Narratives

```python
from narrative_generator import generate_narratives

narratives = generate_narratives(aggregated)
```

Report: "Narratives generated for all 8 sections"

### Step 6: Render HTML Report

```python
from report_renderer import render_report

report_path = render_report(narratives, aggregated, start_date, end_date)
```

Report: "Report saved to {report_path}"

### Step 7: Open in Browser

```bash
open {report_path}
```

Report: "Report opened in browser!"

## Error Handling

- If date parsing fails: show the error and suggest valid formats
- If no sessions found: report clearly with the date range used
- If facet generation fails for some sessions: continue with what succeeded
- If narrative generation fails: use fallback narratives (the module handles this internally)
- If report rendering fails: show the error and the path to the aggregated data

## Notes

- All Python scripts are at `~/.codex/skills/my-insights/scripts/`
- Facets are cached at `~/.codex/usage-data/facets/{session_id}.json` — re-runs are fast
- The report is saved to `~/.codex/usage-data/report-{start}-{end}.html`
- The facet generator may still require a local LLM adapter. If it is not configured, skip facet enrichment and continue with aggregate-only reporting.
- Each facet batch costs ~0.01-0.03 in API calls; full generation for ~1300 sessions costs ~$3-6
