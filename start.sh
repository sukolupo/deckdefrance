#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "Stopping any running deckdefrance uvicorn sessions..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

echo "Starting deckdefrance in production mode..."
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
