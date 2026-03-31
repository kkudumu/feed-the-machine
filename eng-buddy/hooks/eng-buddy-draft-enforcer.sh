#!/bin/bash
# Hook: Draft enforcer for eng-buddy
# Trigger: UserPromptSubmit
# Purpose: When user asks for a draft (Slack message, email, status update, etc.),
#          inject a reminder to write it to a markdown file FIRST, then show the content.
#
# The eng-buddy SKILL.md Communication Drafts Protocol requires:
#   1. Write the file to ~/.claude/eng-buddy/drafts/ BEFORE showing any draft content
#   2. Include metadata at top (Date, Channel, To)
#   3. Return the full file path in chat, then show the draft content
#
# This hook enforces that mechanically so Claude can't skip the file write.

# Check if eng-buddy session is active
if [ ! -f ~/.claude/eng-buddy/.session-active ]; then
    exit 0
fi

# Read payload from stdin
STDIN_DATA=$(cat)
USER_MESSAGE=$(echo "$STDIN_DATA" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('prompt', ''))
except:
    print('')
" 2>/dev/null)

# Convert to lowercase for matching
MSG_LOWER=$(echo "$USER_MESSAGE" | tr '[:upper:]' '[:lower:]')

# Check for draft-related keywords
DRAFT_MATCH=false
for keyword in "draft" "write me a" "write this" "write a message" "compose" "draft a" "draft for" "draft to" "draft update" "draft email" "draft slack" "draft comms" "draft response" "write a response" "help me write" "what do i say" "what should i say"; do
    if echo "$MSG_LOWER" | grep -qi "$keyword"; then
        DRAFT_MATCH=true
        break
    fi
done

if [ "$DRAFT_MATCH" = "true" ]; then
    cat <<'DRAFT_EOF'
[DRAFT PROTOCOL ENFORCED]: The user is asking for a draft/message/communication.

BEFORE showing any draft content in chat, you MUST:
1. Determine the filename: [recipient]-[topic]-[YYYY-MM-DD].md
2. Write the file to ~/.claude/eng-buddy/drafts/ using the Write tool
3. Include metadata at top: Date, Channel, To
4. THEN return the full file path in chat
5. THEN show the draft content

DO NOT show the draft text first and save later. File write comes FIRST.
DRAFT_EOF
fi
