#!/usr/bin/env bash
set -uo pipefail
TOKEN="hf_XXX_PUT_YOUR_TOKEN_HERE"
DST="$HOME/models/Qwen2.5-3B-Instruct-AWQ"
mkdir -p "$DST"
FILES="config.json generation_config.json merges.txt model.safetensors tokenizer.json tokenizer_config.json vocab.json"
for f in $FILES; do
  if [ -s "$DST/$f" ]; then
    echo "  [skip] $f"
    continue
  fi
  echo "  [dl] $f"
  curl -sL -H "Authorization: Bearer $TOKEN" --retry 4 --retry-delay 3 --max-time 3600 \
    -o "$DST/$f.part" "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-AWQ/resolve/main/$f" \
    && mv "$DST/$f.part" "$DST/$f" && echo "  [ok] $f" \
    || echo "  [WARN] failed: $f"
done
echo "==== Q3 DONE ===="
ls -lh "$DST"
