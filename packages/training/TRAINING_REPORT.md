# Source Tier LoRA 训练报告 (2026-05-18)

## 环境搭建

| 组件 | 状态 |
|------|------|
| PyTorch 2.12.0+cu128 | ✅ SJTU 镜像安装成功 |
| RTX 5060 (sm_120) | ✅ Blackwell 架构完全支持 |
| VS Build Tools 2022 | ✅ MSVC 编译器就绪 |
| Unsloth 2026.5.2 | ✅ Triton kernel 编译通过 |
| deepseek-r1:7b (Ollama) | ✅ 4.7GB 已下载 |
| qwen2.5:7b (Ollama) | ✅ 可用 |

## 训练执行

- 基座模型: DeepSeek-R1-Distill-Qwen-7B-bnb-4bit
- LoRA: r=16, alpha=32, dropout=0, 全层 (28 QKV+O+MLP)
- 数据集: 564 train / 120 val / 125 test
- 训练: 3 epochs, batch=2, grad_accum=8, bf16
- 耗时: 17 分钟, 108 steps
- Loss: 3.637 → 0.331
- 模型: 154MB adapter_model.safetensors

## 评估结果

| Tier  | 规则基线 | qwen2.5 few-shot | LoRA R1-7B (3ep) |
|-------|---------|-------------------|-------------------|
| A     | 100%    | 80.0%             | 100%              |
| B     | 100%    | 77.8%             | **5.6%** ⚠        |
| C     | 6.7%    | 46.7%             | 46.7%             |
| D     | 93.8%   | 75.0%             | 18.8%             |
| 总体  | 88.0%   | 74.4%             | 42.4%             |

## 根因分析

LoRA 模型 B 级崩溃 (100%→5.6%) 原因:
1. 训练集不平衡: A+B 占 75.7%, C 仅 11.9%, D 仅 12.4%
2. A/B 都使用 .gov.cn 域名, 仅凭 domain+url+title 无法区分
3. 规则分类器本身就是 A/B 最优方案 (确定性规则 100%)

## 结论: Hybrid 三层架构为最优解

- Layer 3 (硬规则): 覆盖 60-70% 案例 (A/B/D)
- 模型: 处理规则未覆盖的 C 级 + 边界案例
- 当前可用: hard_rules + qwen2.5:7b 组合, 预期准确率 85%+

## 后续计划
1. 数据增强: 增加 C/D 训练样本, 添加 B 级 hard negative
2. 降低 lr (1e-4), 减少 epochs (2), 增加数据量 (目标 2000+)
3. 探索: content-based 特征 (snippet/extracted_text) 改善 C 级判断
