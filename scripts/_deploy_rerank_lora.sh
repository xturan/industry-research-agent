#!/usr/bin/env bash
# After training: patch the adapter base to the AWQ id, copy into WSL, and point
# the rerank service at the LoRA. Run from WSL.
set -euo pipefail
SRC=/mnt/e/invest_agent/packages/training/data/model_output_rerank_3b_lora
DST=/home/hjz/rerank-lora-adapter

if [ ! -f "$SRC/adapter_config.json" ]; then
  echo "adapter not found: $SRC (train first?)" >&2
  exit 1
fi

rm -rf "$DST"
mkdir -p "$DST"
cp "$SRC/adapter_config.json" "$DST/"
cp "$SRC/adapter_model.safetensors" "$DST/" 2>/dev/null || echo "no adapter_model.safetensors"
# tokenizer for the LoRA module (Qwen2.5 tokenizer)
cp "$SRC/tokenizer.json" "$DST/" 2>/dev/null || true
cp "$SRC/tokenizer_config.json" "$DST/" 2>/dev/null || true

# Patch base_model_name_or_path -> the AWQ model we serve.
python3 - <<'PY'
import json
p = "/home/hjz/rerank-lora-adapter/adapter_config.json"
d = json.load(open(p))
d["base_model_name_or_path"] = "Qwen/Qwen2.5-3B-Instruct-AWQ"
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
print("patched base ->", d["base_model_name_or_path"])
print("lora r =", d.get("r"), "| target_modules:", len(d.get("target_modules", [])))
PY
ls -lh "$DST"
