"""Deploy the retrieval LLM reranker + embedding services with vLLM.

Starts two local vLLM OpenAI-compatible servers:
  A. LLM reranker (chat): --model <base> --lora-modules
     source-quality-v2=<adapter>  -> port 8000 (RERANK_ENDPOINT)
  B. embedding model (e.g. bge-m3): --model <model> --task embed
     -> port 8001 (EMBEDDING_ENDPOINT)

Usage (run each in its own terminal):
  python scripts/deploy_vllm_rerank_embed.py --rerank
  python scripts/deploy_vllm_rerank_embed.py --embed

Or just print the commands:
  python scripts/deploy_vllm_rerank_embed.py --print-only
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RERANK_ADAPTER = (
    REPO / "packages" / "training" / "data" / "model_output_v8_dpo_from_v7_b005_lr2e6"
)


def _rerank_command(base_model: str, port: int) -> list[str]:
    if not RERANK_ADAPTER.exists():
        print(f"[warn] adapter not found: {RERANK_ADAPTER}", file=sys.stderr)
    return [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", base_model,
        "--lora-modules", f"source-quality-v2={RERANK_ADAPTER}",
        "--port", str(port),
        "--max-model-len", "8192",
    ]


def _embed_command(model: str, port: int) -> list[str]:
    return [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model,
        "--task", "embed",
        "--port", str(port),
        "--max-model-len", "8192",
    ]


def _health_check(endpoint: str) -> bool:
    import urllib.request

    base = endpoint.rsplit("/v1", 1)[0] if "/v1" in endpoint else endpoint
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy vLLM reranker + embedding services")
    parser.add_argument("--rerank", action="store_true", help="start LLM reranker")
    parser.add_argument("--embed", action="store_true", help="start embedding model")
    parser.add_argument("--print-only", action="store_true", help="only print the commands")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct",
                        help="base model for the LLM-reranker QLoRA adapter")
    parser.add_argument("--embed-model", default="BAAI/bge-m3", help="embedding model name")
    parser.add_argument("--rerank-port", type=int, default=8000)
    parser.add_argument("--embed-port", type=int, default=8001)
    args = parser.parse_args()

    commands: list[tuple[str, list[str]]] = []
    if args.rerank:
        commands.append(("rerank", _rerank_command(args.base_model, args.rerank_port)))
    if args.embed:
        commands.append(("embed", _embed_command(args.embed_model, args.embed_port)))
    if not commands:
        commands = [
            ("rerank", _rerank_command(args.base_model, args.rerank_port)),
            ("embed", _embed_command(args.embed_model, args.embed_port)),
        ]

    print("=== vLLM 部署命令 ===")
    for name, cmd in commands:
        print(f"\n[{name}]")
        print("  " + " ".join(cmd))

    if args.print_only:
        return 0

    if not shutil.which("vllm") and not shutil.which("python"):
        print("vllm 未找到，请先 pip install vllm", file=sys.stderr)
        return 1

    for name, cmd in commands:
        print(f"\n启动 [{name}] ... (Ctrl-C 停止)")
        try:
            subprocess.run(cmd, check=False)
        except KeyboardInterrupt:
            print(f"[{name}] 已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
