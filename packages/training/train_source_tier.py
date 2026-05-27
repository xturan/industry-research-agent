"""Standard QLoRA fine-tuning — no Unsloth, no fused CE, works on 8GB VRAM.

Base:  unsloth/DeepSeek-R1-Distill-Qwen-7B-bnb-4bit (pre-quantized, cached)
Load:  transformers.AutoModelForCausalLM (reads bitsandbytes config from model)
LoRA:  peft.LoraConfig r=16 alpha=32
Train: trl.SFTTrainer (standard PyTorch CE loss, no custom kernels)

Dataset: source_tier_train_v2.jsonl (640 CoT samples, 100% content)
GPU:     RTX 5060 8GB — model=5.2GB, training buffers≈2.5GB, fits in 8GB

Usage:
    python -m packages.training.train_source_tier --epochs 3 --batch 2 --grad-accum 8
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TRAIN_FILE = DATA_DIR / "source_tier_train_v2.jsonl"
OUTPUT_DIR = DATA_DIR / "model_output_v2"

# Pre-quantized bitsandbytes model (5.2GB, already cached)
BASE_MODEL = "unsloth/DeepSeek-R1-Distill-Qwen-7B-bnb-4bit"


def load_dataset_jsonl(filepath: Path) -> list[dict]:
    samples = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    return samples


def format_prompt(sample: dict) -> str:
    """Alpaca format preserving CoT in output."""
    return (
        f"### Instruction:\n{sample['instruction']}\n\n"
        f"### Input:\n{sample['input']}\n\n"
        f"### Response:\n{sample['output']}"
    )


def train(epochs: int = 3, batch_size: int = 2, grad_accum: int = 8):
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTTrainer, SFTConfig

    print(f"[INFO] Loading model: {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    model.config.pad_token_id = tokenizer.pad_token_id
    model.config.use_cache = False

    vram_mb = torch.cuda.memory_allocated() / 1024**2
    print(f"[INFO] VRAM used: {vram_mb:.0f} MB")

    model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable()

    print("[INFO] Applying LoRA (r=16, alpha=32, dropout=0.05)...")
    lora_config = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none", task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    print(f"[INFO] Loading {TRAIN_FILE}")
    train_data = load_dataset_jsonl(TRAIN_FILE)
    train_texts = [{"text": format_prompt(s)} for s in train_data]
    train_dataset = Dataset.from_list(train_texts)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    training_args = SFTConfig(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=1e-4,
        warmup_steps=15,
        max_length=1024,
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
        model=model, processing_class=tokenizer,
        train_dataset=train_dataset,
        args=training_args,
    )

    total_steps = len(train_data) * epochs // (batch_size * grad_accum)
    print(f"[INFO] {len(train_data)} samples × {epochs} epochs")
    print(f"[INFO] batch={batch_size}, grad_accum={grad_accum}, effective={batch_size * grad_accum}")
    print(f"[INFO] ~{total_steps} steps, lr=1e-4, bf16=True")

    trainer.train()

    print(f"[INFO] Saving LoRA → {OUTPUT_DIR}")
    model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print("[DONE]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    args = parser.parse_args()
    train(args.epochs, args.batch, args.grad_accum)


if __name__ == "__main__":
    main()
