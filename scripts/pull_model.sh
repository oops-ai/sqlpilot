#!/bin/sh
set -eu

OLLAMA_BIN="/Applications/Ollama.app/Contents/Resources/ollama"
MODEL="${OLLAMA_MODEL:-qwen2.5-coder:1.5b}"

if [ ! -x "$OLLAMA_BIN" ]; then
  echo "Ollama is not installed at $OLLAMA_BIN"
  exit 1
fi

"$OLLAMA_BIN" pull "$MODEL"
