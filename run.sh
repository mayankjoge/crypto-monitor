#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3.10+ and run this script again." >&2
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  "$PYTHON_BIN" -m venv .venv
fi
if ! .venv/bin/python -c 'import flask, requests' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi
export MOCK_MODE="${MOCK_MODE:-1}"
exec .venv/bin/python app.py
