#!/usr/bin/env bash
export HF_HUB_OFFLINE=1
export VLLM_WSL2_ENABLE_PIN_MEMORY=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export CC=/usr/bin/gcc
export CXX=/usr/bin/g++
exec ~/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
  --model /home/hjz/models/Qwen2.5-7B-Instruct-AWQ \
  --quantization awq \
  --enable-lora \
  --max-lora-rank 32 \
  --lora-modules source-quality-v2=/home/hjz/rerank-adapter \
  --port 8000 \
  --max-model-len 1536 \
  --gpu-memory-utilization 0.82 \
  --attention-backend FLASH_ATTN \
  --enforce-eager \
  --no-enable-flashinfer-autotune \
  --compilation-config '{"mode": "NONE"}'
