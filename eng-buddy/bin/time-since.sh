#!/bin/bash
# Calculate time elapsed since a given ISO timestamp
# Usage: time-since.sh "2026-01-26T14:50:00"

if [ -z "$1" ]; then
    echo "Usage: time-since.sh <ISO-timestamp>"
    echo "Example: time-since.sh '2026-01-26T14:50:00'"
    exit 1
fi

# Get timestamps
past_time=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$1" +%s 2>/dev/null)
current_time=$(date +%s)

if [ -z "$past_time" ]; then
    echo "Error: Invalid timestamp format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
    exit 1
fi

# Calculate difference
diff=$((current_time - past_time))

# Convert to human readable
days=$((diff / 86400))
hours=$(((diff % 86400) / 3600))
minutes=$(((diff % 3600) / 60))

# Output
echo "Time since $1:"
if [ $days -gt 0 ]; then
    echo "  $days days, $hours hours, $minutes minutes"
    echo "  (${diff} seconds total)"
elif [ $hours -gt 0 ]; then
    echo "  $hours hours, $minutes minutes"
    echo "  (${diff} seconds total)"
else
    echo "  $minutes minutes"
    echo "  (${diff} seconds total)"
fi
