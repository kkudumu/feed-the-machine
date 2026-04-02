#!/usr/bin/env bash
# run-knip.sh — Run knip and return structured findings
# Exit 0 if clean, 1 if findings exist

set -euo pipefail

# Check for package.json
if [ ! -f "package.json" ]; then
  echo '{"skipped": true, "reason": "No package.json found"}'
  exit 0
fi

# Run knip with JSON reporter
OUTPUT=$(npx knip --reporter json 2>/dev/null || true)

# Check if output is empty or just '{}'
if [ -z "$OUTPUT" ] || [ "$OUTPUT" = "{}" ] || [ "$OUTPUT" = '{"files":[],"issues":[]}' ]; then
  echo '{"clean": true, "files": [], "issues": []}'
  exit 0
fi

echo "$OUTPUT"
exit 1
