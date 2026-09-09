#!/usr/bin/env bash
# Download Qwen2.5-3B-Instruct bf16 base for LoRA training, via curl (proxy-safe).
set -uo pipefail
TOKEN="hf_XXX_PUT_YOUR_TOKEN_HERE"
DST="/e/invest_agent/models/Qwen2.5-3B-Instruct"
mkdir -p "$DST"
FILES="config.json generation_config.json merges.txt model-00001-of-00002.safetensors model-00002-of-00002.safetensors model.safetensors.index.json tokenizer.json tokenizer_config.json vocab.json"
for f in $FILES; do
  if [ -s "$DST/$f" ]; then
    echo "  [skip] $f"
    continue
  fi
  echo "  [dl] $f"
  curl -sL -H "Authorization: Bearer $TOKEN" --retry 4 --retry-delay 3 --max-time 3600 \
    -o "$DST/$f.part" "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/resolve/main/$f" \
    && mv "$DST/$f.part" "$DST/$f" && echo "  [ok] $f" \
    || echo "  [WARN] failed: $f"
done
echo "==== DONE ===="
ls -lh "$DST"
