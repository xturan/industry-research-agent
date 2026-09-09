# Rerank LoRA/OPD 训练交接文档

## 目标

本轮训练目标是提升 Invest Agent 在产业研究检索链路中的 rerank 能力：给定一个研究 query 和一批候选网页/PDF chunk，模型输出 `0-4` 五档相关性分数，用于将更有证据价值的 chunk 排到前面。

标签含义：

- `0`: 无关
- `1`: 弱相关
- `2`: 一般相关
- `3`: 相关且有实质信息
- `4`: 核心证据

最终推荐版本：

```text
output/rerank_3b_lora_v6_opd_clean/checkpoint-120
```

绝对路径：

```text
/home/amax/Projects/invest/invest-agent/data/rerank_cloud_train/output/rerank_3b_lora_v6_opd_clean/checkpoint-120
```

## 基座与训练环境

基座模型：

```text
Qwen/Qwen2.5-3B-Instruct
```

训练方式：

- QLoRA / LoRA adapter
- 4-bit bnb 加载基座
- `torchrun` 双卡分布式训练
- 训练硬件：2 × RTX 4090
- 注意：当前环境没有安装 `deepspeed`，因此 rerank 本轮实际使用的是 `torchrun` DDP，不是 DeepSpeed。

主要脚本：

```text
train_rerank_lora_cloud.py      # SFT 训练入口
train_rerank_opd_lora.py        # OPD pairwise 训练入口
eval_rerank_lora.py             # eval 入口
build_rerank_opd_pairs.py       # OPD pair 构造
build_boundary34_calibration.py # 3/4 边界校准数据构造
score_rerank_alpaca.py          # 对训练集打分，用于 hard mining
build_hard_opd_pairs.py         # hard OPD pair 挖掘
```

## 数据集

### SFT 训练集

```text
data/v2_alpaca_balanced.jsonl
```

规模：

```text
2660 条
```

格式：Alpaca

```json
{
  "instruction": "...",
  "input": "查询：...\n\n文档：...",
  "output": "0-4",
  "query_id": "...",
  "level": "...",
  "chunk_id": "...",
  "source_family": "...",
  "score": 0.85,
  "relation": "..."
}
```

原始标签分布：

```text
0: 399
1: 532
2: 532
3: 532
4: 665
```

### Eval 集

```text
data_eval/eval_label.jsonl
```

规模：

```text
98 条
```

评估方式：

- 对每条 eval 样本构造 `query + chunk` prompt
- 取模型下一个 token 在 `0/1/2/3/4` 五个 digit token 上的概率
- 预测概率最高的 bucket
- 计算：
  - exact accuracy
  - within-1 accuracy
  - MAE bucket
  - mean nDCG@5
  - mean nDCG@10
  - `>=3` 二分类指标
  - `>=4` 核心证据召回

## 实验演进

### 1. Base 模型评估

基座：

```text
Qwen/Qwen2.5-3B-Instruct
```

结果：

```text
exact: 28.57%
within-1: 71.43%
MAE: 1.0714
nDCG@5: 0.6866
nDCG@10: 0.8247
>=3 F1: 0.6038
>=4 recall: 0.00%
```

结论：基座具备一定语义判断能力，但不会稳定输出项目定义的 0-4 rerank 桶，不能直接作为 reranker。

### 2. v3 SFT LoRA

训练集：

```text
data/v2_alpaca_balanced.jsonl
```

输出：

```text
output/rerank_3b_lora_v3_ddp_2x4090_len1536
```

训练命令核心参数：

```text
epochs: 4
batch: 2
grad_accum: 4
world_size: 2
effective_batch: 16
max_length: 1536
lr: 2e-4
LoRA rank: 16
completion_only: true
```

结果：

```text
exact: 39.80%
within-1: 92.86%
MAE: 0.6735
nDCG@5: 0.7454
nDCG@10: 0.8606
>=3 F1: 0.8529
>=4 recall: 9.38%
```

结论：

- SFT 明显提升了整体分桶能力。
- 但模型对 `4` 类非常保守，大量 gold 4 被预测为 3。
- 这说明问题不是“不会判断相关”，而是 `3/4` 核心证据边界不够清晰。

### 3. v4 Boundary 3/4 校准实验

目的：通过重复 4 类样本提高核心证据召回。

构造数据：

```text
data/v3_boundary34_calibration.jsonl
```

规模：

```text
2274 条
```

分布：

```text
0: 96
1: 96
2: 220
3: 532
4: 1330
```

输出：

```text
output/rerank_3b_lora_v4_boundary34
```

结果：

```text
exact: 39.80%
within-1: 91.84%
MAE: 0.6837
nDCG@5: 0.7171
nDCG@10: 0.8535
>=4 recall: 6.25%
```

结论：失败实验。

单纯重复 4 类样本没有解决 3/4 边界，反而降低了 nDCG 和 4 类召回。说明不能只靠标签重采样，需要让模型学习同 query 下的相对排序关系。

### 4. v5 OPD Pairwise 训练

方法定义：

```text
OPD = Ordinal Preference Distillation
```

核心思想：

同一个 query 下，高标签 chunk 应该排在低标签 chunk 前面。

构造 pair：

```text
4 > 3
4 > 2
3 > 2
2 > 1
1 > 0
```

数据：

```text
data/v4_opd_pairs.jsonl
```

规模：

```text
3124 对
```

分布：

```text
4>3: 1220
3>2: 604
4>2: 540
1>0: 390
2>1: 370
```

训练入口：

```text
train_rerank_opd_lora.py
```

初始化：

```text
output/rerank_3b_lora_v3_ddp_2x4090_len1536
```

输出：

```text
output/rerank_3b_lora_v5_opd
```

最佳 checkpoint：

```text
output/rerank_3b_lora_v5_opd/checkpoint-120
```

结果：

```text
exact: 43.88%
within-1: 92.86%
MAE: 0.6327
nDCG@5: 0.7434
nDCG@10: 0.8688
>=3 F1: 0.8615
>=4 recall: 18.75%
```

结论：

- OPD 有效提升了 exact、MAE、nDCG@10 和 4 类召回。
- 但 nDCG@5 基本没有超过 v3，说明 top-5 排序还需要更干净的数据。

### 5. v6 Clean OPD

动机：

训练集中存在大量超长网页 chunk：

```text
p50: 2049 chars
p90: 4816 chars
p95: 14544 chars
p99: 69859 chars
max: 346165 chars
```

这些超长文档在 `max_length=1536` 下会被截断，模型常常只能看到网页开头、导航、免责声明、推荐内容，而不是和 query 真正相关的段落。

处理方式：

在 `build_rerank_opd_pairs.py` 中加入 query-aware 文档压缩：

- 保留文档头部
- 抽取 query 关键词附近窗口
- 最大压缩到 `6000` 字符

clean pair 数据：

```text
data/v5_opd_pairs_clean.jsonl
```

规模：

```text
3124 对
```

压缩情况：

```text
chosen compressed: 149
rejected compressed: 225
max chars: 6000
p99 chars: 6000
```

初始化：

```text
output/rerank_3b_lora_v5_opd/checkpoint-120
```

输出：

```text
output/rerank_3b_lora_v6_opd_clean
```

最佳 checkpoint：

```text
output/rerank_3b_lora_v6_opd_clean/checkpoint-120
```

结果：

```text
exact: 47.96%
within-1: 90.82%
MAE: 0.6122
nDCG@5: 0.7545
nDCG@10: 0.8785
>=3 F1: 0.8657
>=4 recall: 31.25%
```

结论：

这是当前最优版本。

相比 v3 SFT：

```text
exact: 39.80% -> 47.96%
MAE: 0.6735 -> 0.6122
nDCG@5: 0.7454 -> 0.7545
nDCG@10: 0.8606 -> 0.8785
>=4 recall: 9.38% -> 31.25%
```

### 6. v7 Hard OPD Mining

目的：从当前最佳模型中挖掘它仍然分不清的 hard pair，再做短程训练。

步骤：

1. 使用 v6 checkpoint-120 对原始训练集 `2660` 条样本打分。
2. 根据模型期望分数找出同 query 下 chosen 没有明显高于 rejected 的 pair。
3. 构造 hard pair 数据。

打分输出：

```text
output/rerank_3b_lora_v6_opd_clean/train_v2_scores.jsonl
```

hard pair 数据：

```text
data/v6_opd_pairs_hard_mined.jsonl
```

规模：

```text
473 对
```

分布：

```text
4>3: 135
3>2: 119
1>0: 85
2>1: 70
4>2: 64
```

输出：

```text
output/rerank_3b_lora_v7_hard_opd
```

结果：

```text
v7 checkpoint-40:
exact: 42.86%
MAE: 0.6531
nDCG@5: 0.7524
nDCG@10: 0.8697
>=4 recall: 15.62%

v7 final:
exact: 42.86%
MAE: 0.6633
nDCG@5: 0.7524
nDCG@10: 0.8689
>=4 recall: 15.62%
```

结论：失败实验。

Hard mining 数据太少且过于集中，继续训练导致泛化回退。v7 不建议接入。

## 最终结果对比

| 版本 | exact | MAE | nDCG@5 | nDCG@10 | >=4 recall |
|---|---:|---:|---:|---:|---:|
| Base | 28.57% | 1.0714 | 0.6866 | 0.8247 | 0.00% |
| v3 SFT | 39.80% | 0.6735 | 0.7454 | 0.8606 | 9.38% |
| v4 3/4 Boundary | 39.80% | 0.6837 | 0.7171 | 0.8535 | 6.25% |
| v5 OPD ckpt-120 | 43.88% | 0.6327 | 0.7434 | 0.8688 | 18.75% |
| v6 Clean OPD ckpt-120 | 47.96% | 0.6122 | 0.7545 | 0.8785 | 31.25% |
| v7 Hard OPD ckpt-40 | 42.86% | 0.6531 | 0.7524 | 0.8697 | 15.62% |

## 最优版本

推荐接入：

```text
output/rerank_3b_lora_v6_opd_clean/checkpoint-120
```

不推荐：

```text
output/rerank_3b_lora_v7_hard_opd
output/rerank_3b_lora_v7_hard_opd/checkpoint-40
```

原因：

- v6 clean OPD 在 exact、MAE、nDCG@5、nDCG@10、4 类召回上综合最优。
- v7 hard mining 出现回退，说明继续在同一批数据上挖 hard pair 已经收益递减。

## 接入方式

运行时需要：

1. 加载基座：

```text
Qwen/Qwen2.5-3B-Instruct
```

2. 加载 LoRA adapter：

```text
output/rerank_3b_lora_v6_opd_clean/checkpoint-120
```

3. 推理 prompt 格式：

```text
### Instruction:
你是一个产业研究检索精排器。判断下面文档对查询的相关性，输出 0-4 五档分数：0=无关，1=弱相关，2=一般相关，3=相关且有实质信息，4=核心证据。只输出一个数字。

### Input:
查询：{query}

文档：{chunk_text}

### Response:
```

4. 推理方式：

取模型下一个 token 在 `0/1/2/3/4` digit token 上的 logits/probs，选择概率最高的数字作为 bucket。

也可以计算期望分数：

```text
expected_score = sum(prob[i] * i for i in 0..4)
```

用于更细粒度排序。

建议排序策略：

```text
primary: expected_score
secondary: bucket
```

## 当前瓶颈与后续方向

当前继续训练同一批数据已经收益递减。下一步真正值得做的是：

1. 扩大 query-level eval

当前 eval 只有 `98` 条，建议扩展到：

```text
30-50 个 query
每个 query 20-50 个 candidate chunks
总 eval 600-1500 条
```

重点评估：

```text
nDCG@5
nDCG@10
Recall@5 for gold>=4
Recall@10 for gold>=3
MRR
```

2. 构造 listwise 数据

当前 OPD 是 pairwise。真实 rerank 是 listwise：一个 query 对应一组候选 chunk。后续可以按 query 构造完整候选列表，直接优化列表排序目标。

3. 补充真实 hard negative

尤其需要同 query 下的：

```text
chosen = 政策原文 / 年报公告 / 招投标公告 / 统计原表 / 企业订单证据
rejected = 新闻转述 / 泛行业评论 / 弱相关政策 / 营销稿
```

4. 固化 query-aware 清洗

v6 的提升说明网页清洗非常重要。后续 ingestion/rerank 训练都应保留：

```text
标题 + 正文前部 + query 关键词附近窗口
删除导航、免责声明、相关推荐、版权声明
```

## 一句话结论

本轮 rerank 训练从 SFT 分类模型演进到 OPD 偏好排序模型，并通过 query-aware 清洗解决超长网页噪声问题。当前最优版本是：

```text
output/rerank_3b_lora_v6_opd_clean/checkpoint-120
```

它相对 v3 SFT 显著提升了整体分桶准确率、排序质量和核心证据召回，是当前推荐接入 Deep Research / rerank 运行时的定版候选。
