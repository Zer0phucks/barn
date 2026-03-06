#!/usr/bin/env bash
set -euo pipefail

PROJECT_REF="${VPT_SUPABASE_PROJECT_REF:-vzgmmlaojvkpbakvgcwh}"
WORKER_PORT="${VPT_WORKER_PORT:-5000}"
TUNNEL_HOST="${VPT_TUNNEL_HOST:-https://loca.lt}"
RETRY_SECONDS="${VPT_TUNNEL_RETRY_SECONDS:-3}"

NPX_BIN="${NPX_BIN:-$(command -v npx || true)}"
SUPABASE_BIN="${SUPABASE_BIN:-$(command -v supabase || true)}"

if [[ -z "$SUPABASE_BIN" && -x "/home/linuxbrew/.linuxbrew/bin/supabase" ]]; then
  SUPABASE_BIN="/home/linuxbrew/.linuxbrew/bin/supabase"
fi

if [[ -z "$NPX_BIN" && -x "/usr/bin/npx" ]]; then
  NPX_BIN="/usr/bin/npx"
fi

if [[ -z "$NPX_BIN" ]]; then
  echo "[vpt-tunnel] npx not found; install Node.js/npm first"
  exit 1
fi

if [[ -z "$SUPABASE_BIN" ]]; then
  echo "[vpt-tunnel] supabase CLI not found in PATH"
  exit 1
fi

if [[ -z "${SCOUT_API_KEY:-}" ]]; then
  echo "[vpt-tunnel] SCOUT_API_KEY is required in environment"
  exit 1
fi

while true; do
  echo "[vpt-tunnel] starting tunnel on port ${WORKER_PORT}"
  synced=0

  coproc LT_PROC { "$NPX_BIN" --yes localtunnel --port "$WORKER_PORT" --host "$TUNNEL_HOST" 2>&1; }
  lt_pid=$LT_PROC_PID

  while IFS= read -r line <&"${LT_PROC[0]}"; do
    echo "[localtunnel] $line"

    if [[ "$synced" -eq 0 ]]; then
      url="$(printf '%s\n' "$line" | grep -Eo 'https://[^ ]+' | head -n 1 || true)"
      if [[ -n "$url" ]]; then
        url="${url%/}"
        echo "[vpt-tunnel] detected public URL: ${url}"

        if "$SUPABASE_BIN" secrets set --project-ref "$PROJECT_REF" "VPT_WORKER_BASE_URL=$url"; then
          echo "[vpt-tunnel] synced VPT_WORKER_BASE_URL for project ${PROJECT_REF}"
          synced=1
        else
          echo "[vpt-tunnel] failed to sync VPT_WORKER_BASE_URL"
        fi
      fi
    fi
  done

  wait "$lt_pid" || true
  echo "[vpt-tunnel] tunnel exited; retrying in ${RETRY_SECONDS}s"
  sleep "$RETRY_SECONDS"
done
