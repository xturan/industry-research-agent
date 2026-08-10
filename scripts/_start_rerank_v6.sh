#!/usr/bin/env bash
# Serve the recommended v6 clean-OPD reranker LoRA via vLLM (WSL, RTX 5060 8GB).
#
# Uses the CACHED AWQ 3B base (/home/hjz/models/Qwen2.5-3B-Instruct-AWQ) because
# the BF16 base is not cached locally and 8GB VRAM fits the AWQ variant better.
# The v6 adapter (base=Qwen/Qwen2.5-3B-Instruct BF16) is copied to
# /home/hjz/rerank-lora-adapter-v6 and its base_model_name_or_path patched to the
# AWQ id — same pattern as _deploy_rerank_lora.sh.
#
# LoRA name: rerank-lora (so the app's default RERANK_MODEL=rerank-lora works).
# After it is up: RERANK_ENDPOINT=http://localhost:8000/v1/chat/completions
set -euo pipefail

export HF_HUB_OFFLINE=1
export VLLM_WSL2_ENABLE_PIN_MEMORY=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export CC=/usr/bin/gcc
export CXX=/usr/bin/g++

SRC=/mnt/e/invest_agent/data/rerank_cloud_train/output/rerank_3b_lora_v6_opd_clean/checkpoint-120
DST=/home/hjz/rerank-lora-adapter-v6
BASE_DIR=/home/hjz/models/Qwen2.5-3B-Instruct-AWQ

if [ ! -f "$SRC/adapter_model.safetensors" ]; then
  echo "v6 adapter not found at $SRC (adapter_model.safetensors missing)" >&2
  exit 1
fi

rm -rf "$DST"
mkdir -p "$DST"
cp "$SRC/adapter_config.json" "$DST/"
cp "$SRC/adapter_model.safetensors" "$DST/"
cp "$SRC/tokenizer.json" "$DST/" 2>/dev/null || true
cp "$SRC/tokenizer_config.json" "$DST/" 2>/dev/null || true

# Patch base_model_name_or_path -> the AWQ model we serve.
python3 - <<'PY'
import json
p = "/home/hjz/rerank-lora-adapter-v6/adapter_config.json"
d = json.load(open(p))
d["base_model_name_or_path"] = "Qwen/Qwen2.5-3B-Instruct-AWQ"
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
print("patched base ->", d["base_model_name_or_path"])
print("lora r =", d.get("r"), "| target_modules:", len(d.get("target_modules", [])))
PY

exec ~/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
  --model "$BASE_DIR" \
  --quantization awq \
  --enable-lora \
  --max-lora-rank 16 \
  --lora-modules rerank-lora="$DST" \
  --served-model-name Qwen2.5-3B-Instruct-AWQ \
  --port 8000 \
  --max-model-len 1536 \
  --gpu-memory-utilization 0.45 \
  --attention-backend FLASH_ATTN \
  --enforce-eager \
  --no-enable-flashinfer-autotune \
  --compilation-config '{"mode": "NONE"}'
