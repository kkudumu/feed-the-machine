# Timestamp Format Guide

## MANDATORY FORMAT: ISO 8601

All timestamps in Engineering Buddy files MUST use ISO 8601 format:
```
YYYY-MM-DDTHH:MM:SS
```

## Examples

**Correct**:
- Email sent: 2026-01-26T14:50:00
- Meeting started: 2026-01-27T09:30:00
- Task completed: 2026-01-26T15:45:30

**Incorrect** (DO NOT USE):
- Email sent (~2:50 PM)
- Meeting started around 9:30 AM
- Task completed this afternoon
- Yesterday at 3pm

## Why ISO Format?

1. **No timezone ambiguity**: Always local time for consistency
2. **Calculable**: Can use bash/tools to calculate "time since"
3. **Sortable**: Chronological order preserved
4. **Parseable**: No hallucination risk - exact timestamp

## Time Calculations

Use the helper script:
```bash
~/.claude/eng-buddy/bin/time-since.sh "2026-01-26T14:50:00"
```

## Quick Reference

Current time:
```bash
date +%Y-%m-%dT%H:%M:%S
```

Time since event:
```bash
~/.claude/eng-buddy/bin/time-since.sh "2026-01-26T14:50:00"
```

## Engineering Buddy Protocol

**Before claiming any elapsed time**:
1. Get current time: `date +%Y-%m-%dT%H:%M:%S`
2. Run time-since.sh with ISO timestamp
3. Use calculated result, not estimated

**Never say**: "36 hours ago", "a few days ago", "last week"
**Always say**: "Started: 2026-01-26T14:50:00 (16 hours 38 minutes ago based on calculation)"
