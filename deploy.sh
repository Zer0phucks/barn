#!/bin/bash
set -e

REPO_DIR="/home/nsnfrd768/barn/barn"

echo "==> Pulling latest..."
cd "$REPO_DIR"
git pull origin main

echo "==> Building web..."
cd "$REPO_DIR/web"
npm install --silent
npm run build

echo "==> Restarting barn-scan service..."
sudo systemctl restart barn-scan

echo "==> Deploy complete."
