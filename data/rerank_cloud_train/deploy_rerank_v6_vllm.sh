#!/usr/bin/env bash
# Serve the recommended reranker (v6 clean-OPD LoRA) via vLLM OpenAI server.
#
# Run on the GPU machine (Linux; 2x RTX 4090 validated). The LoRA weights are
# expected at CHECKPOINT_DIR (default: this repo's
# data/rerank_cloud_train/output/rerank_3b_lora_v6_opd_clean/checkpoint-120,
# which is already synced). Override with CHECKPOINT_DIR for other hosts.
#
# After this is up:
#   export RERANK_ENDPOINT=http://<host>:8000/v1/chat/completions
#   export RERANK_MODEL=rerank-lora
set -euo pipefail

BASE_MODEL=${BASE_MODEL:-Qwen/Qwen2.5-3B-Instruct}
# Name that the app's RERANK_MODEL must match.
LORA_NAME=${LORA_NAME:-rerank-lora}
# Absolute path to the merged adapter dir (must contain adapter_model.safetensors).
# Default: the synced v6 checkpoint inside this repo (data/rerank_cloud_train/output/...).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_CHECKPOINT="$SCRIPT_DIR/output/rerank_3b_lora_v6_opd_clean/checkpoint-120"
CHECKPOINT_DIR=${CHECKPOINT_DIR:-$DEFAULT_CHECKPOINT}
PORT=${PORT:-8000}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-1536}
PYTHON=${PYTHON:-python}

if [ ! -f "$CHECKPOINT_DIR/adapter_model.safetensors" ]; then
  echo "adapter weights not found at $CHECKPOINT_DIR (adapter_model.safetensors missing)." >&2
  echo "Sync the cloud checkpoint first, e.g.:" >&2
  echo "  rsync -av amax@<host>:~/invest-agent/data/rerank_cloud_train/output/rerank_3b_lora_v6_opd_clean/checkpoint-120/ \"$CHECKPOINT_DIR/\"" >&2
  exit 1
fi

exec "$PYTHON" -m vllm.entrypoints.openai.api_server \
  --model "$BASE_MODEL" \
  --enable-lora \
  --max-lora-rank 16 \
  --lora-modules "$LORA_NAME=$CHECKPOINT_DIR" \
  --served-model-name "$BASE_MODEL" \
  --port "$PORT" \
  --max-model-len "$MAX_MODEL_LEN"
