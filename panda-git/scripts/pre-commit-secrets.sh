#!/usr/bin/env bash
# panda-git pre-commit hook — blocks commits containing hardcoded secrets
# Installed by the panda-git skill on first invocation. Safe to remove with:
#   rm .git/hooks/pre-commit  (or edit to remove the panda-git section)
#
# This hook scans staged files only (fast). The full panda-git skill does
# deeper scanning with context validation and auto-remediation — this is
# the safety net that catches what slips through.

set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Get list of staged files (excluding deletions)
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)
if [ -z "$STAGED_FILES" ]; then
  exit 0
fi

# Skip binary files, lock files, and vendored directories
FILTERED_FILES=""
for f in $STAGED_FILES; do
  case "$f" in
    node_modules/*|vendor/*|.git/*|__pycache__/*|dist/*|build/*) continue ;;
    package-lock.json|yarn.lock|Gemfile.lock|poetry.lock|pnpm-lock.yaml) continue ;;
    *.png|*.jpg|*.gif|*.ico|*.woff|*.woff2|*.ttf|*.eot|*.pdf|*.zip|*.tar*) continue ;;
    .env.example|.env.sample|.env.template) continue ;;
    *) FILTERED_FILES="$FILTERED_FILES $f" ;;
  esac
done

if [ -z "$FILTERED_FILES" ]; then
  exit 0
fi

FOUND=0
FINDINGS=""

# Tier 1: High-confidence patterns — these almost never false-positive
# We scan staged content (not working tree) to catch exactly what would be committed
PATTERNS=(
  'AKIA[0-9A-Z]{16}'                                            # AWS Access Key ID
  'ghp_[A-Za-z0-9_]{36}'                                        # GitHub PAT
  'gho_[A-Za-z0-9_]{36}'                                        # GitHub OAuth
  'ghu_[A-Za-z0-9_]{36}'                                        # GitHub user token
  'ghs_[A-Za-z0-9_]{36}'                                        # GitHub server token
  'github_pat_[A-Za-z0-9_]{82}'                                  # GitHub fine-grained PAT
  'xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}'              # Slack bot token
  'xoxp-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,34}'          # Slack user token
  'xoxa-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,34}'          # Slack app token
  'AIza[0-9A-Za-z\-_]{35}'                                      # Google API key
  'sk_live_[0-9a-zA-Z]{24,}'                                    # Stripe live secret
  'sk_test_[0-9a-zA-Z]{24,}'                                    # Stripe test secret
  'rk_live_[0-9a-zA-Z]{24,}'                                    # Stripe restricted
  'SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}'                 # SendGrid
  'SK[0-9a-fA-F]{32}'                                            # Twilio
  'npm_[A-Za-z0-9]{36}'                                          # npm token
  'glpat-[A-Za-z0-9\-_]{20,}'                                   # GitLab PAT
  '-----BEGIN (RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----'        # Private keys
)

for f in $FILTERED_FILES; do
  # Get the staged version of the file (what would actually be committed)
  CONTENT=$(git show ":$f" 2>/dev/null || true)
  if [ -z "$CONTENT" ]; then
    continue
  fi

  for pattern in "${PATTERNS[@]}"; do
    MATCHES=$(echo "$CONTENT" | grep -nE "$pattern" 2>/dev/null || true)
    if [ -n "$MATCHES" ]; then
      while IFS= read -r match; do
        LINE_NUM=$(echo "$match" | cut -d: -f1)
        # Mask the secret value in output (show first 8 chars only)
        MASKED=$(echo "$match" | cut -d: -f2- | sed -E 's/([A-Za-z0-9_\-]{8})[A-Za-z0-9_\-]{8,}/\1****/g')
        FINDINGS="${FINDINGS}\n  ${RED}BLOCKED${NC}  $f:$LINE_NUM  $MASKED"
        FOUND=$((FOUND + 1))
      done <<< "$MATCHES"
    fi
  done
done

# Also check: is a .env file being committed?
for f in $STAGED_FILES; do
  case "$f" in
    .env|.env.local|.env.production|.env.staging|.env.*.local)
      FINDINGS="${FINDINGS}\n  ${YELLOW}WARNING${NC}  $f is staged — this file typically contains secrets and should be gitignored"
      FOUND=$((FOUND + 1))
      ;;
  esac
done

if [ "$FOUND" -gt 0 ]; then
  echo ""
  echo -e "${RED}panda-git: COMMIT BLOCKED — $FOUND secret(s) detected in staged files${NC}"
  echo ""
  echo -e "$FINDINGS"
  echo ""
  echo "To fix: run /panda-git for auto-remediation, or manually:"
  echo "  1. Move secrets to .env (gitignored)"
  echo "  2. Replace hardcoded values with env var references"
  echo "  3. Stage the cleaned files and commit again"
  echo ""
  echo "To bypass (NOT recommended): git commit --no-verify"
  exit 1
fi

exit 0
