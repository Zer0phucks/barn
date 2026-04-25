#!/usr/bin/env bash
# Trigger a limited Gemini deep-research batch on BARN-scan (for OpenClaw cron or systemd).
# Requires: BARN_SCAN_URL, SCOUT_API_KEY (same value as Flask / Scout app).
#
# Usage: ./openclaw_research_batch.sh [limit] [offset]
# Example: BARN_SCAN_URL=http://127.0.0.1:5000 SCOUT_API_KEY=secret ./openclaw_research_batch.sh 25 0

set -euo pipefail

: "${BARN_SCAN_URL:?Set BARN_SCAN_URL (e.g. http://127.0.0.1:5000)}"
: "${SCOUT_API_KEY:?Set SCOUT_API_KEY to match Flask SCOUT_API_KEY}"

LIMIT="${1:-25}"
OFFSET="${2:-0}"
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || ! [[ "$OFFSET" =~ ^[0-9]+$ ]]; then
  echo "usage: $0 [limit] [offset]  (non-negative integers)" >&2
  exit 1
fi

BASE="${BARN_SCAN_URL%/}"
curl -sS -w "\nHTTP_STATUS:%{http_code}\n" -X POST "${BASE}/api/research/start-batch" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${SCOUT_API_KEY}" \
  -d "{\"limit\": ${LIMIT}, \"offset\": ${OFFSET}}"
