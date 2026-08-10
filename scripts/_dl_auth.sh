#!/usr/bin/env bash
set -uo pipefail
TOKEN="hf_XXX_PUT_YOUR_TOKEN_HERE"

dl() {  # url dest_dir file
  local url="$1" dst="$2" file="$3"
  mkdir -p "$dst"
  if [ -s "$dst/$file" ]; then
    echo "  [skip] $file"
    return 0
  fi
  echo "  [dl] $file"
  rm -f "$dst/$file.part"
  if curl -sL -H "Authorization: Bearer $TOKEN" --retry 4 --retry-delay 3 --max-time 3600 \
      -o "$dst/$file.part" "$url"; then
    mv "$dst/$file.part" "$dst/$file"
    echo "  [ok] $file"
  else
    echo "  [WARN] failed: $file"
  fi
}

echo "==== bge-m3 (2.1GB) ===="
for f in config.json pytorch_model.bin tokenizer.json tokenizer_config.json special_tokens_map.json sentencepiece.bpe.model; do
  dl "https://huggingface.co/BAAI/bge-m3/resolve/main/$f" "$HOME/models/BAAI/bge-m3" "$f"
done

echo "==== Qwen2.5-7B-Instruct-AWQ (4.5GB) ===="
for f in config.json generation_config.json merges.txt model-00001-of-00002.safetensors model-00002-of-00002.safetensors model.safetensors.index.json tokenizer.json tokenizer_config.json vocab.json; do
  dl "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-AWQ/resolve/main/$f" "$HOME/models/Qwen2.5-7B-Instruct-AWQ" "$f"
done

echo "==== ALL DONE ===="
