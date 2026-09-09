# Source Tier LoRA 训练规格说明 — DeepSpeed 分布式版

> 复制本文到 AI 对话框即可开始训练，无需逐条解释。

## 数据集

```
E:\invest_agent\packages\training\data\source_tier_train_v2.jsonl
```

- **样本数:** 640 条
- **格式:** Alpaca (`instruction` / `input` / `output`)
- **output 风格:** CoT 逐步推理（Step 1→2→3→JSON 结论）
- **标注分布:** A/B/C/D 四分类，均衡采样
- **配套验证集:** `source_tier_val_v2.jsonl` (137 条)
- **配套测试集:** `source_tier_test_v2.jsonl` (139 条)
- **特征:** 每条样本带 `domain` / `tier` / `route_type` / `has_content` 元信息，100% 含正文内容

### 样本构建方式（prompt 模板）

```
### Instruction:
{instruction}

### Input:
{input}

### Response:
{output}
```

## 模型

```
基座: unsloth/DeepSeek-R1-Distill-Qwen-7B-bnb-4bit
架构: Qwen2ForCausalLM（DeepSeek R1 蒸馏版）
参数量: 7.6B（基座），4-bit 量化后占用约 5.2 GB
```

**注意:** 基座已经是 bnb 4-bit 量化版。加载时使用 `transformers.AutoModelForCausalLM` 配合 `BitsAndBytesConfig`，不需要额外量化步骤。

## 训练方法

### LoRA 配置

```python
LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    bias="none",
    task_type="CAUSAL_LM",
)
```

- 可训练参数: ~40M / 7.6B ≈ 0.53%
- 训练框架: `trl.SFTTrainer`（标准 PyTorch CE loss，无 custom kernel）

### 超参数

| 参数 | 值 |
|------|-----|
| epochs | 3 |
| per_device_batch_size | 1（DeepSpeed 场景，单卡显存紧张） |
| gradient_accumulation_steps | 16 |
| 有效 batch size | 1 × 16 × N_gpu |
| learning_rate | 1e-4 |
| warmup_steps | 15 |
| max_length | 1024 |
| precision | bf16 |
| seed | 42 |

## DeepSpeed 配置

### 策略选择

单机多卡场景（1 台机器，N 张 GPU），使用 **ZeRO Stage 2**：

- **ZeRO-1**（optimizer states 分片）→ 显存节省最小，不推荐
- **ZeRO-2**（optimizer + gradient 分片）→ 4-bit LoRA 场景性价比最高，推荐
- **ZeRO-3**（参数 + optimizer + gradient 分片）→ 4-bit 量化模型不兼容 / 收益递减，不推荐

### deepspeed_config.json

```json
{
  "zero_optimization": {
    "stage": 2,
    "offload_optimizer": {
      "device": "cpu",
      "pin_memory": true
    },
    "allgather_partitions": true,
    "allgather_bucket_size": 2e8,
    "overlap_comm": true,
    "reduce_scatter": true,
    "reduce_bucket_size": 2e8,
    "contiguous_gradients": true
  },
  "bf16": {
    "enabled": true
  },
  "train_batch_size": "auto",
  "train_micro_batch_size_per_gpu": "auto",
  "gradient_accumulation_steps": "auto",
  "wall_clock_breakdown": false
}
```

### 为什么 ZeRO-2 而非 ZeRO-3

1. **4-bit 量化模型与 ZeRO-3 参数分片冲突** — bnb 的量化参数不能直接分片后再重组，需要额外适配层
2. **LoRA 可训练参数只有 40M** — optimizer states 本身很小，ZeRO-2 的分片收益已足够
3. **CPU offload 兜底** — optimizer states 溢出到 CPU 内存（32GB 主存绰绰有余）

### 硬件环境

| 硬件 | 规格 |
|------|------|
| GPU | RTX 5060 Laptop × 1（当前单卡；DeepSpeed 可扩展到多卡） |
| VRAM | 8 GB / 卡 |
| CPU | i9-14900HX（32 GB RAM，支持 optimizer CPU offload） |
| CUDA | 12.8（PyTorch 2.12.0 nightly） |

### 训练总步数估算

```
单卡: 640 samples × 3 epochs ÷ (1 batch × 16 grad_accum) ≈ 120 steps
2 卡: 640 × 3 ÷ (1 × 16 × 2) ≈ 60 steps
4 卡: 640 × 3 ÷ (1 × 16 × 4) ≈ 30 steps
```

### 启动命令

```bash
# 单机单卡（回退方案，已验证可行）
python -m packages.training.train_source_tier --epochs 3 --batch 1 --grad-accum 16

# 单机多卡（DeepSpeed）
deepspeed --num_gpus=2 packages/training/train_deepspeed.py \
  --epochs 3 --batch 1 --grad-accum 16 \
  --deepspeed packages/training/deepspeed_config.json

# 或使用 torchrun（兼容性更广）
torchrun --nproc_per_node=2 packages/training/train_deepspeed.py \
  --epochs 3 --batch 1 --grad-accum 16 \
  --deepspeed packages/training/deepspeed_config.json
```

## 训练脚本改造要点（待实现）

当前 `train_source_tier.py` 用的是 `device_map="auto"`（单卡），DeepSpeed 需要：

1. **移除 `device_map="auto"`** — DeepSpeed 自己管设备分配
2. **`SFTConfig` 增加 `deepspeed` 参数** — 指向上面的 json
3. **可选：peft 训练省显存技巧**
   ```python
   model = prepare_model_for_kbit_training(model)
   model.gradient_checkpointing_enable()
   ```
   trl 的 SFTTrainer 已支持 `--deepspeed` 透传

## 输出

```
输出目录: E:\invest_agent\packages\training\data\model_output_v3_deepspeed\
输出文件:
  - adapter_config.json   # LoRA 配置
  - adapter_model.safetensors  # LoRA 权重 (~150 MB)
  - tokenizer 相关文件
```

## 验证

训练完成后运行:

```bash
# 评估模型
python -m packages.training.eval_source_tier \
  --model-dir packages/training/data/model_output_v3_deepspeed

# 对比基线
#   规则基线:  A 100%  B 100%  C 6.7%   D 93.8%  → 总体 88.0%
#   v2 LoRA:   A  80%  B  78%  C 47%    D  75%   → 总体 74.4%
#   DeepSpeed 版目标:  C ≥ 50%, 总体 ≥ 78%
```
