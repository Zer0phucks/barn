#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/noob/barn}"
BRANCH="${BRANCH:-main}"
SCAN_DIR="${REPO_DIR}/scan"
WEB_DIR="${REPO_DIR}/web"
SYSTEMD_USER_DIR="${SYSTEMD_USER_DIR:-${HOME}/.config/systemd/user}"
if command -v /usr/bin/python3 >/dev/null 2>&1; then
  DEFAULT_PYTHON_BIN="/usr/bin/python3"
else
  DEFAULT_PYTHON_BIN="python3"
fi
PYTHON_BIN="${PYTHON_BIN:-${DEFAULT_PYTHON_BIN}}"
PULL_CHANGES=1
INSTALL_PLAYWRIGHT=0

log() {
  printf '[redeploy] %s\n' "$1"
}

usage() {
  cat <<'EOF'
Usage: scripts/redeploy_local.sh [--skip-pull] [--install-playwright]

Refreshes the local BARN deployment by:
  1. Fast-forwarding the repo to origin/main
  2. Rebuilding the Python virtualenv if needed
  3. Installing scan/web dependencies
  4. Installing the user systemd units
  5. Restarting the worker and tunnel services

Options:
  --skip-pull            Do not fetch/pull before rebuilding
  --install-playwright   Also install Chromium for Playwright
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-pull)
      PULL_CHANGES=0
      ;;
    --install-playwright)
      INSTALL_PLAYWRIGHT=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  printf 'Repo not found at %s\n' "$REPO_DIR" >&2
  exit 1
fi

mkdir -p "$SYSTEMD_USER_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  printf 'Python interpreter not found: %s\n' "$PYTHON_BIN" >&2
  exit 1
fi

if [[ "$PULL_CHANGES" -eq 1 ]]; then
  log "Fetching latest ${BRANCH}"
  git -C "$REPO_DIR" fetch origin "$BRANCH"
  git -C "$REPO_DIR" checkout "$BRANCH"
  git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"
else
  log "Skipping git pull"
fi

if [[ -L "${SCAN_DIR}/.venv" && ! -e "${SCAN_DIR}/.venv" ]]; then
  log "Removing stale .venv symlink"
  rm "${SCAN_DIR}/.venv"
fi

EXPECTED_PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
CURRENT_VENV_VERSION=""
if [[ -x "${SCAN_DIR}/.venv/bin/python" ]]; then
  CURRENT_VENV_VERSION="$("${SCAN_DIR}/.venv/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
fi

if [[ ! -x "${SCAN_DIR}/.venv/bin/python" || "$CURRENT_VENV_VERSION" != "$EXPECTED_PYTHON_VERSION" ]]; then
  log "Creating local scan virtualenv"
  rm -rf "${SCAN_DIR}/.venv"
  "$PYTHON_BIN" -m venv "${SCAN_DIR}/.venv"
fi

log "Installing Python dependencies"
"${SCAN_DIR}/.venv/bin/pip" install --upgrade pip
"${SCAN_DIR}/.venv/bin/pip" install -r "${SCAN_DIR}/requirements.txt"

if [[ "$INSTALL_PLAYWRIGHT" -eq 1 ]]; then
  log "Installing Playwright Chromium"
  "${SCAN_DIR}/.venv/bin/python" -m playwright install chromium
fi

log "Installing web dependencies"
npm --prefix "$WEB_DIR" install --silent

log "Building web app"
npm --prefix "$WEB_DIR" run build

log "Installing user service units"
install -m 0644 "${SCAN_DIR}/service/barn-vpt-worker.service" "${SYSTEMD_USER_DIR}/barn-vpt-worker.service"
install -m 0644 "${SCAN_DIR}/service/barn-vpt-tunnel.service" "${SYSTEMD_USER_DIR}/barn-vpt-tunnel.service"

log "Reloading systemd user daemon"
systemctl --user daemon-reload

log "Enabling BARN services"
systemctl --user enable barn-vpt-worker.service barn-vpt-tunnel.service

log "Restarting BARN services"
systemctl --user restart barn-vpt-worker.service
systemctl --user restart barn-vpt-tunnel.service

log "Deployment complete"
