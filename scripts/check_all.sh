#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
    echo "error: expected executable Python at $PYTHON" >&2
    echo "create the environment with: python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'" >&2
    exit 1
fi

PYTHON_CMD=(env -u MANGOHUD -u PYTHONPATH "$PYTHON")

echo "== pytest =="
"${PYTHON_CMD[@]}" -m pytest citybuilder/tests tests -q

echo "== offscreen screenshots =="
"${PYTHON_CMD[@]}" -m citybuilder --screenshot docs/verification \
    --angles 0,45,90

echo "== 12-angle rotation sweep =="
"${PYTHON_CMD[@]}" -m pytest citybuilder/tests/test_rotation_sweep.py -q

echo "check_all: PASS"
