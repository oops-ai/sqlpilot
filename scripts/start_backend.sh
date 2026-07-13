#!/bin/sh
set -eu

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
