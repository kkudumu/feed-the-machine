# eng-buddy Hook Installation Guide

## Overview

The eng-buddy skill includes a seven-hook automation system that handles automatic progress logging, context preservation across compaction, session snapshots, heartbeat monitoring, and learning-engine completion capture. All hooks are session-gated — they only activate during active `/eng-buddy` sessions and deactivate automatically when the conversation ends.

## Installation Steps

### 1. Run the Hook Installer (Recommended)

Use the one-shot installer to sync hooks to all relevant parent/child locations and patch settings:

```bash
bash ~/.claude/skills/eng-buddy/bin/install-hooks.sh
```

What this does automatically:
- Installs hooks to `~/.claude/hooks` (runtime parent hooks)
- Syncs hooks to `~/.claude/skills/eng-buddy/hooks` (skill child copy)
- Syncs hooks to `~/.claude/eng-buddy/hooks` (runtime child copy)
- Patches `~/.claude/settings.json` for `UserPromptSubmit`, `PostToolUse`, and `SessionEnd`
- Ensures learning-engine runtime files exist (`~/.claude/eng-buddy/bin/brain.py`)

### 1b. Manual Copy (Optional, if you don't use installer)

**Find your hooks directory:**
- **Claude Code default**: `~/.claude/hooks/`
- **Custom setup**: Check your `settings.json` for `CLAUDE_HOME` environment variable

**Copy the hooks:**

```bash
# For default Claude Code setup:
cp ~/.claude/skills/eng-buddy/hooks/*.sh ~/.claude/hooks/

# For custom CLAUDE_HOME setup:
cp ~/.claude/skills/eng-buddy/hooks/*.sh $CLAUDE_HOME/hooks/
```

**Make them executable:**

```bash
chmod +x ~/.claude/hooks/eng-buddy-*.sh
# Or for custom CLAUDE_HOME:
chmod +x $CLAUDE_HOME/hooks/eng-buddy-*.sh
```

### 2. Update Your settings.json

**Location:**
- Default: `~/.claude/settings.json`
- Custom: `$CLAUDE_HOME/settings.json`

**Add hook configuration:**

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/.claude/hooks/eng-buddy-pre-compaction.sh"
          },
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/.claude/hooks/eng-buddy-post-compaction.sh"
          },
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/.claude/hooks/eng-buddy-auto-log.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/.claude/hooks/eng-buddy-learning-capture.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/.claude/hooks/eng-buddy-session-snapshot.sh"
          },
          {
            "type": "command",
            "command": "/Users/YOUR_USERNAME/.claude/hooks/eng-buddy-session-end.sh"
          }
        ]
      }
    ]
  }
}
```

**⚠️ Replace `/Users/YOUR_USERNAME/` with your actual home directory path!**

**⚠️ SessionEnd ordering is critical**: `eng-buddy-session-snapshot.sh` MUST be listed before `eng-buddy-session-end.sh`. The snapshot reads `.session-active`; session-end removes it.

### 3. Update SKILL.md Paths

Open `~/.claude/skills/eng-buddy/SKILL.md` and find **STEP 0** in the "Workspace Initialization Protocol" section.

**Update the path to match your hooks directory:**

```
STEP 0: Install/sync hooks, then activate auto-logging (MUST DO FIRST)
- Use Bash: bash ~/.claude/skills/eng-buddy/bin/install-hooks.sh
- Use Bash: /Users/YOUR_USERNAME/.claude/hooks/eng-buddy-session-manager.sh start
```

**Replace with your actual hooks path.**

### 4. Verify Installation

```bash
# Run installer again safely (idempotent):
bash ~/.claude/skills/eng-buddy/bin/install-hooks.sh

# Check hooks are in place and executable:
ls -la ~/.claude/hooks/eng-buddy-*.sh
ls -la ~/.claude/skills/eng-buddy/hooks/eng-buddy-*.sh
ls -la ~/.claude/eng-buddy/hooks/eng-buddy-*.sh

# Optional: run the repo sync check (from ~/.claude repo root):
make eng-buddy-check-hooks

# Check session manager works:
~/.claude/hooks/eng-buddy-session-manager.sh status
```

You should see: `⏸️  eng-buddy auto-logging is INACTIVE`

## How It Works

### When You Invoke `/eng-buddy`

1. **STEP 0 activates** → Runs `eng-buddy-session-manager.sh start`
2. **Creates marker file** → `~/.claude/eng-buddy/.session-active`
3. **All hooks are now active** → Monitor messages, compaction events, and session state

### During Your Session (on every user message)

Three hooks fire on every `UserPromptSubmit`:

1. **pre-compaction**: Checks if the context window is approaching its limit — if so, silently writes current session state to the daily log before compaction occurs.

2. **post-compaction**: Checks if context was just compacted (conversation was summarized). If detected, injects a reminder for Claude to reload your workspace context from the daily log.

3. **auto-log**: Detects progress update phrases ("I completed...", "I sent...", "I fixed...", etc.) and reminds Claude to log the action. Also runs the heartbeat check (~30-minute intervals) to surface items from `HEARTBEAT.md`.

### During Tool Execution (after every tool call)

`eng-buddy-learning-capture.sh` fires on `PostToolUse`:

1. Captures completion events for `Write/Edit/Bash/task-style MCP` tools into `inbox.db` (`learning_events` table).
2. Routes known categories (e.g. `writing-update`, `task-execution`) into learning files.
3. If a completion cannot be mapped, Claude asks whether to add a new category.
4. If you approve, run:
   ```bash
   python3 ~/.claude/eng-buddy/bin/brain.py \
     --register-learning-category \"your-category\" \
     --description \"What this captures\"
   ```

### When Session Ends

1. **session-snapshot fires first** → Reads the session JSONL, filters to meaningful user/assistant exchanges, captures the last 15 as a dated markdown file in `sessions/`
2. **session-end fires second** → Removes `.session-active` marker
3. **All hooks deactivate** → Won't fire in other conversations

## Hook Files Explained

### eng-buddy-session-manager.sh
- **Trigger**: Called manually by SKILL.md STEP 0 (not wired as a hook)
- **Purpose**: Gate all other hooks — creates/removes `.session-active` marker
- **Commands**:
  - `start` - Activates session (creates marker file)
  - `stop` - Deactivates session (removes marker file)
  - `status` - Check if session is active

### eng-buddy-pre-compaction.sh
- **Trigger**: UserPromptSubmit (every user message)
- **Purpose**: Silently flush session state to daily log before context window fills
- **Only runs when**: `.session-active` marker file exists
- **How**: Checks approaching token limit; if near threshold, writes summary to daily log

### eng-buddy-post-compaction.sh
- **Trigger**: UserPromptSubmit (every user message)
- **Purpose**: Detect context compaction and restore workspace state
- **Only runs when**: `.session-active` marker file exists
- **How**: Checks for compaction signals; if detected, injects context reload reminder

### eng-buddy-auto-log.sh
- **Trigger**: UserPromptSubmit (every user message)
- **Purpose**: Detect progress updates and prompt logging; run heartbeat checks
- **Only runs when**: `.session-active` marker file exists
- **Detection patterns**: "I completed", "I sent", "I fixed", "just merged", etc.
- **Heartbeat**: Also surfaces items from `HEARTBEAT.md` on ~30-minute intervals

### eng-buddy-learning-capture.sh
- **Trigger**: PostToolUse (after each tool call)
- **Purpose**: Capture write/task completion events into learning engine DB (`learning_events`, `learning_categories`)
- **Session scope**: Active `/eng-buddy` sessions and dashboard-opened `eng-buddy task` sessions
- **Category behavior**:
  - Known mapping → auto-route to learning files
  - Unknown mapping → asks user if a new category should be registered

### eng-buddy-session-snapshot.sh
- **Trigger**: SessionEnd (when conversation ends)
- **Purpose**: Capture last 15 meaningful exchanges as a dated markdown snapshot
- **Only runs when**: `.session-active` marker file exists
- **Output**: `~/.claude/eng-buddy/sessions/YYYY-MM-DDTHH-MM-topic.md`
- **Minimum**: Requires ≥3 meaningful messages; skips trivial sessions
- **⚠️ Must run BEFORE `eng-buddy-session-end.sh`** in settings.json

### eng-buddy-session-end.sh
- **Trigger**: SessionEnd (when conversation ends)
- **Purpose**: Auto-deactivate all hooks when session ends
- **Action**: Removes `.session-active` marker file
- **⚠️ Must run AFTER `eng-buddy-session-snapshot.sh`** in settings.json

## Troubleshooting

### Hook Not Triggering

**Check if active:**
```bash
~/.claude/hooks/eng-buddy-session-manager.sh status
```

**Manually activate:**
```bash
~/.claude/hooks/eng-buddy-session-manager.sh start
```

**Check marker file exists:**
```bash
ls -la ~/.claude/eng-buddy/.session-active
```

### Hook Triggering in Other Conversations

The hook should ONLY fire during eng-buddy sessions. If it's firing elsewhere:

1. Check if marker file exists when it shouldn't:
   ```bash
   rm ~/.claude/eng-buddy/.session-active
   ```

2. Verify SessionEnd hook is configured in settings.json

3. Restart Claude Code

### Hook Scripts Not Found

Verify paths in settings.json match where you copied the hooks:

```bash
# Check your hooks directory:
ls -la ~/.claude/hooks/eng-buddy-*.sh

# Or for custom CLAUDE_HOME:
ls -la $CLAUDE_HOME/hooks/eng-buddy-*.sh
```

Update settings.json paths to match actual location.

## Customization

### Adjust Detection Patterns

Edit `eng-buddy-auto-log.sh` to add/remove action patterns:

```bash
ACTION_PATTERNS=(
    "^[Ii] (completed?|finished|fixed)"
    "^[Jj]ust (completed?|finished|fixed)"
    # Add your own patterns here
)
```

### Change Session Marker Location

Default: `~/.claude/eng-buddy/.session-active`

To change, edit all three hook scripts and update the path.

## Uninstallation

To remove the auto-logging system:

1. **Remove hooks:**
   ```bash
   rm ~/.claude/hooks/eng-buddy-*.sh
   ```

2. **Remove settings.json configuration:**
   - Delete the `UserPromptSubmit`, `PostToolUse`, and `SessionEnd` hook entries

3. **Remove marker file:**
   ```bash
   rm ~/.claude/eng-buddy/.session-active
   ```

The eng-buddy skill will still work without hooks - you just won't get automatic logging prompts.

---

## Support

**Issues?** Check:
1. Hook scripts are executable (`chmod +x`)
2. Paths in settings.json are absolute and correct
3. Marker file exists during active sessions
4. SessionEnd hook is configured for auto-cleanup

**Questions?** Open an issue in the eng-buddy repository.
