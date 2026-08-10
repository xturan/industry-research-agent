#!/usr/bin/env bash
set -uo pipefail

dl() {  # repo file dest_dir
  local repo="$1" file="$2" dst="$3"
  mkdir -p "$dst"
  if [ -s "$dst/$file" ]; then
    echo "  [skip] $file"
    return 0
  fi
  local url="https://huggingface.co/${repo}/resolve/main/${file}"
  echo "  [dl] $file"
  curl -sL -C - --retry 3 --retry-delay 2 --max-time 900 -o "$dst/$file" "$url" || echo "  [WARN] failed: $file"
}

echo "==== bge-m3 ===="
BGE=~/models/BAAI/bge-m3
for f in config.json pytorch_model.bin tokenizer.json tokenizer_config.json special_tokens_map.json sentencepiece.bpe.model; do
  dl "BAAI/bge-m3" "$f" "$BGE"
done

echo "==== Qwen2.5-7B-Instruct-AWQ ===="
QWEN=~/models/Qwen2.5-7B-Instruct-AWQ
curl -sL --max-time 20 "https://huggingface.co/api/models/Qwen/Qwen2.5-7B-Instruct-AWQ" -o /tmp/qwen_list.json
python3 - <<'PY'
import json
try:
    d = json.load(open("/tmp/qwen_list.json"))
except Exception as e:
    print("list FAIL", e); raise SystemExit(0)
skip = {".gitattributes", "README.md", "LICENSE", "onnx"}
for s in d.get("siblings", []):
    f = s["rfilename"]
    if f in skip or f.startswith("onnx/"):
        continue
    print(f)
PY
