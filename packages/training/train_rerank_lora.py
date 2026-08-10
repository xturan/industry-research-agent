"""QLoRA fine-tuning for the fine-grained relevance-scoring reranker.

Base:  Qwen/Qwen2.5-3B-Instruct (bf16, QLoRA 4-bit via bitsandbytes)
Data:  data/rerank_training/train_alpaca.jsonl (DeepSeek-labeled, score|reason)
Format: Alpaca (instruction/input/output), output = "<0.87> | <reason>"
GPU:   RTX 5060 8GB — 3B QLoRA fits comfortably.

Usage:
    python -m packages.training.train_rerank_lora --epochs 4 --batch 2 --grad-accum 8
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
DATA_DIR = _REPO / "data" / "rerank_training"
TRAIN_FILE = DATA_DIR / "v2_alpaca_balanced.jsonl"
OUTPUT_DIR = Path(__file__).parent / "data" / "model_output_rerank_3b_lora_v2"

# Local bf16 base (download via scripts/_dl_qwen_bf16.sh) to avoid HF-downloader
# hangs; loaded fully offline.
BASE_MODEL = str(_REPO / "models" / "Qwen2.5-3B-Instruct")


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and value:
            os.environ.setdefault(name, value)


def load_dataset_jsonl(filepath: Path) -> list[dict]:
    samples = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    return samples


def format_prompt(sample: dict) -> str:
    return (
        f"### Instruction:\n{sample['instruction']}\n\n"
        f"### Input:\n{sample['input']}\n\n"
        f"### Response:\n{sample['output']}"
    )


def train(
    epochs: int = 4,
    batch_size: int = 2,
    grad_accum: int = 8,
    max_length: int = 1024,
    lr: float = 2e-4,
    max_lora_rank: int = 16,
    data_file: Path | None = None,
    output_dir: Path | None = None,
):
    train_file = data_file or TRAIN_FILE
    out_dir = output_dir or OUTPUT_DIR
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from trl import SFTConfig, SFTTrainer

    print(f"[INFO] Loading model: {BASE_MODEL}")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    model.config.pad_token_id = tokenizer.pad_token_id
    model.config.use_cache = False

    vram_mb = torch.cuda.memory_allocated() / 1024**2
    print(f"[INFO] VRAM used after load: {vram_mb:.0f} MB")

    model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable()

    print(f"[INFO] Applying LoRA (r={max_lora_rank}, alpha={2 * max_lora_rank}, dropout=0.05)...")
    lora_config = LoraConfig(
        r=max_lora_rank,
        lora_alpha=2 * max_lora_rank,
        lora_dropout=0.05,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    print(f"[INFO] Loading {train_file}")
    train_data = load_dataset_jsonl(train_file)
    train_texts = [{"text": format_prompt(s)} for s in train_data]
    train_dataset = Dataset.from_list(train_texts)

    out_dir.mkdir(parents=True, exist_ok=True)

    training_args = SFTConfig(
        output_dir=str(out_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=lr,
        warmup_steps=20,
        max_length=max_length,
        bf16=True,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=2,
        seed=42,
        remove_unused_columns=False,
        dataloader_pin_memory=False,
        dataset_text_field="text",
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        args=training_args,
    )

    total_steps = len(train_data) * epochs // (batch_size * grad_accum)
    print(f"[INFO] {len(train_data)} samples × {epochs} epochs")
    print(f"[INFO] batch={batch_size}, grad_accum={grad_accum}, effective={batch_size * grad_accum}")
    print(f"[INFO] ~{total_steps} steps, lr={lr}, max_length={max_length}, bf16=True")

    trainer.train()

    print(f"[INFO] Saving LoRA → {out_dir}")
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    # Record the base model name for later vLLM LoRA mounting.
    (out_dir / "base_model_name.txt").write_text(BASE_MODEL, encoding="utf-8")
    print("[DONE]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--data-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--env-file", type=Path, default=_REPO / ".env")
    args = parser.parse_args()

    _load_env(args.env_file)
    # Authenticated HF base download (faster + higher rate limits).
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token

    train(
        args.epochs, args.batch, args.grad_accum, args.max_length, args.lr,
        data_file=args.data_file, output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
