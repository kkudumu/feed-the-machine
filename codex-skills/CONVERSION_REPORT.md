# Codex Skill Conversion Report

Converted 27 skills into `~/feed-the-machine/codex-skills`.

## Converted Skills

- `eng-buddy` from `~/feed-the-machine/eng-buddy`
- `finance-buddy` from `~/.claude/skills/finance-buddy`
- `ftm` from `~/feed-the-machine/ftm`
- `ftm-audit` from `~/feed-the-machine/ftm-audit`
- `ftm-brainstorm` from `~/feed-the-machine/ftm-brainstorm`
- `ftm-browse` from `~/feed-the-machine/ftm-browse`
- `ftm-capture` from `~/feed-the-machine/ftm-capture`
- `ftm-codex-gate` from `~/feed-the-machine/ftm-codex-gate`
- `ftm-config` from `~/feed-the-machine/ftm-config`
- `ftm-council` from `~/feed-the-machine/ftm-council`
- `ftm-dashboard` from `~/feed-the-machine/ftm-dashboard`
- `ftm-debug` from `~/feed-the-machine/ftm-debug`
- `ftm-diagram` from `~/feed-the-machine/ftm-diagram`
- `ftm-executor` from `~/feed-the-machine/ftm-executor`
- `ftm-git` from `~/feed-the-machine/ftm-git`
- `ftm-intent` from `~/feed-the-machine/ftm-intent`
- `ftm-map` from `~/feed-the-machine/ftm-map`
- `ftm-mind` from `~/feed-the-machine/ftm-mind`
- `ftm-pause` from `~/feed-the-machine/ftm-pause`
- `ftm-researcher` from `~/feed-the-machine/ftm-researcher`
- `ftm-resume` from `~/feed-the-machine/ftm-resume`
- `ftm-retro` from `~/feed-the-machine/ftm-retro`
- `ftm-routine` from `~/feed-the-machine/ftm-routine`
- `ftm-upgrade` from `~/feed-the-machine/ftm-upgrade`
- `my-insights` from `~/.claude/skills/my-insights`
- `skill-creator` from `~/.claude/skills/skill-creator`
- `sso-buddy` from `~/feed-the-machine/sso-buddy`

## Skipped Manifests

These Claude manifest files did not have a matching skill directory with `SKILL.md`:

- `freelance-buddy`
- `sso-buddy`

## Remaining Portability Warnings

These counts show where Claude-specific assumptions still remain after the automated pass.

- `eng-buddy`: claude_home_refs=8, claude_cli_refs=10, anthropic_refs=1
- `ftm-brainstorm`: claude_cli_refs=1
- `ftm-council`: anthropic_refs=2
- `ftm-debug`: claude_cli_refs=6
- `ftm-git`: claude_cli_refs=1
- `ftm-mind`: claude_cli_refs=1
- `ftm-researcher`: claude_cli_refs=2
- `my-insights`: claude_home_refs=12, claude_cli_refs=11
- `skill-creator`: claude_home_refs=4, claude_cli_refs=19, anthropic_refs=2
