"""Export fine-tuned LoRA model to GGUF and register with Ollama.

Usage:
    python -m packages.training.export_to_ollama [--output-dir ./model_gguf]
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
LORA_DIR = DATA_DIR / "model_output"
GGUF_DIR = DATA_DIR / "model_gguf"
MODEL_NAME = "source-tier-r1"

MODELFILE_TEMPLATE = """FROM {gguf_path}

PARAMETER temperature 0.1
PARAMETER num_predict 512
PARAMETER stop "<|im_end|>"
PARAMETER stop "</s>"

SYSTEM \"\"\"你是一个信息源分级专家。根据信息源的域名、URL、标题和内容片段，判断其可信度等级和权威性。

分级标准：
A级: 政府官方政策原文（法规、通知、规划、实施细则）
B级: 政府新闻/公共资源交易平台、企业公告、上市公司披露
C级: 行业协会、研究机构、政策解读、咨询报告
D级: 商业媒体、自媒体、聚合器、严重过时源

只返回JSON格式结果。\"\"\"
"""


def merge_and_export_gguf(output_dir: Path):
    """Merge LoRA adapter with base model and export to GGUF."""
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        print("[ERROR] unsloth not installed. Run: pip install unsloth")
        return None

    if not LORA_DIR.exists():
        print(f"[ERROR] LoRA adapter not found at {LORA_DIR}")
        print("  Run training first: python -m packages.training.train_source_tier")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Loading LoRA adapter from {LORA_DIR}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(LORA_DIR),
        max_seq_length=1024,
        load_in_4bit=True,
    )

    gguf_path = output_dir / f"{MODEL_NAME}.Q4_K_M.gguf"
    print(f"[INFO] Exporting to GGUF: {gguf_path}")
    model.save_pretrained_gguf(
        str(output_dir),
        tokenizer,
        quantization_method="q4_k_m",
    )

    # Find the actual GGUF file (unsloth may name it differently)
    gguf_files = list(output_dir.glob("*.gguf"))
    if gguf_files:
        actual_path = gguf_files[0]
        if actual_path != gguf_path:
            actual_path.rename(gguf_path)
        print(f"[INFO] GGUF exported: {gguf_path}")
        return gguf_path
    else:
        print("[ERROR] No GGUF file found after export")
        return None


def create_modelfile(gguf_path: Path) -> Path:
    """Create Ollama Modelfile."""
    modelfile_path = gguf_path.parent / "Modelfile"
    content = MODELFILE_TEMPLATE.format(gguf_path=gguf_path.name)
    modelfile_path.write_text(content, encoding="utf-8")
    print(f"[INFO] Modelfile created: {modelfile_path}")
    return modelfile_path


def register_with_ollama(modelfile_path: Path):
    """Register model with Ollama."""
    print(f"[INFO] Registering model '{MODEL_NAME}' with Ollama...")
    try:
        result = subprocess.run(
            ["ollama", "create", MODEL_NAME, "-f", str(modelfile_path)],
            capture_output=True, text=True, cwd=str(modelfile_path.parent),
        )
        if result.returncode == 0:
            print(f"[DONE] Model '{MODEL_NAME}' registered successfully!")
            print(f"  Test with: ollama run {MODEL_NAME}")
        else:
            print(f"[ERROR] ollama create failed: {result.stderr}")
    except FileNotFoundError:
        print("[ERROR] 'ollama' command not found. Is Ollama installed?")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=GGUF_DIR)
    args = parser.parse_args()

    gguf_path = merge_and_export_gguf(args.output_dir)
    if gguf_path is None:
        return

    modelfile_path = create_modelfile(gguf_path)
    register_with_ollama(modelfile_path)


if __name__ == "__main__":
    main()
