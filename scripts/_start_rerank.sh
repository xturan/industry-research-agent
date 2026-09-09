#!/usr/bin/env bash
# Rerank service — Qwen2.5-3B-Instruct-AWQ + trained reranker LoRA.
# LoRA name: rerank-lora (adapter at ~/rerank-lora-adapter, base patched to AWQ).
# Both the base (baseline) and the LoRA are served on :8000.
export HF_HUB_OFFLINE=1
export VLLM_WSL2_ENABLE_PIN_MEMORY=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export CC=/usr/bin/gcc
export CXX=/usr/bin/g++
exec ~/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
  --model /home/hjz/models/Qwen2.5-3B-Instruct-AWQ \
  --quantization awq \
  --enable-lora \
  --max-lora-rank 16 \
  --lora-modules rerank-lora=/home/hjz/rerank-lora-adapter \
  --served-model-name Qwen2.5-3B-Instruct-AWQ \
  --port 8000 \
  --max-model-len 1536 \
  --gpu-memory-utilization 0.45 \
  --attention-backend FLASH_ATTN \
  --enforce-eager \
  --no-enable-flashinfer-autotune \
  --compilation-config '{"mode": "NONE"}'
