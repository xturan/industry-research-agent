#!/usr/bin/env bash
# Deploy vLLM reranker + bge-m3 embedding in WSL2 Ubuntu (run from Windows:
#   wsl -d Ubuntu ./scripts/deploy_vllm_wsl.sh --embed
#   wsl -d Ubuntu ./scripts/deploy_vllm_wsl.sh --rerank
# Services bind localhost:8001 (embed) / localhost:8000 (rerank); the Windows
# research harness reaches them via WSL2 localhost forwarding.
set -euo pipefail

ADAPTER=/mnt/e/invest_agent/packages/training/data/model_output_v8_dpo_from_v7_b005_lr2e6
PIP_INDEX="${PIP_INDEX:--i https://pypi.tuna.tsinghua.edu.cn/simple}"

echo "[1/4] 安装 python3-venv / python3-pip（需要 sudo 密码）"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip

echo "[2/4] 创建 venv"
python3 -m venv ~/vllm-env
~/vllm-env/bin/pip install --upgrade pip -q

echo "[3/4] 安装 vllm（较大，可能数分钟）"
~/vllm-env/bin/pip install ${PIP_INDEX} vllm

echo "[4/4] 启动服务"
case "${1:-}" in
  --embed)
    ~/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
      --model BAAI/bge-m3 --task embed --port 8001 --max-model-len 8192
    ;;
  --rerank)
    if [ ! -d "$ADAPTER" ]; then
      echo "adapter 不存在: $ADAPTER" >&2
      exit 1
    fi
    ~/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
      --model Qwen/Qwen2.5-7B-Instruct \
      --lora-modules "source-quality-v2=$ADAPTER" \
      --port 8000 --max-model-len 8192
    ;;
  *)
    echo "用法: wsl -d Ubuntu ./scripts/deploy_vllm_wsl.sh [--embed|--rerank]"
    exit 1
    ;;
esac
