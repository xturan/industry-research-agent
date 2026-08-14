#!/usr/bin/env bash
export HF_HUB_OFFLINE=1
export VLLM_WSL2_ENABLE_PIN_MEMORY=1
exec ~/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
  --model /home/hjz/models/BAAI/bge-m3 \
  --convert embed \
  --served-model-name BAAI/bge-m3 \
  --port 8001 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.8 \
  --enforce-eager
