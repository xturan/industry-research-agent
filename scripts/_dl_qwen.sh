#!/usr/bin/env bash
set -uo pipefail
QWEN=~/models/Qwen2.5-7B-Instruct-AWQ
mkdir -p "$QWEN"
FILES="config.json generation_config.json merges.txt model-00001-of-00002.safetensors model-00002-of-00002.safetensors model.safetensors.index.json tokenizer.json tokenizer_config.json vocab.json"
for f in $FILES; do
  if [ -s "$QWEN/$f" ]; then
    echo "  [skip] $f"
    continue
  fi
  echo "  [dl] $f"
  curl -sL -C - --retry 3 --retry-delay 2 --max-time 1800 -o "$QWEN/$f" "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-AWQ/resolve/main/$f" \
    && echo "  [ok] $f" || echo "  [WARN] failed: $f"
done
echo "==== Qwen done, listing ===="
ls -lh "$QWEN"
