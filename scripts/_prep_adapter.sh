#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/e/invest_agent/packages/training/data/model_output_v8_dpo_from_v7_b005_lr2e6
DST=/home/hjz/rerank-adapter
rm -rf "$DST"
mkdir -p "$DST"
cp "$SRC/adapter_config.json" "$DST/"
cp "$SRC/adapter_model.safetensors" "$DST/"
cp -r "$SRC/tokenizer.json" "$DST/" 2>/dev/null || true
cp "$SRC/tokenizer_config.json" "$DST/" 2>/dev/null || true
cp "$SRC/chat_template.jinja" "$DST/" 2>/dev/null || true
python3 - <<'PY'
import json
p = "/home/hjz/rerank-adapter/adapter_config.json"
d = json.load(open(p))
d["base_model_name_or_path"] = "Qwen/Qwen2.5-7B-Instruct-AWQ"
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
print("patched base ->", d["base_model_name_or_path"])
PY
ls -lh "$DST"
