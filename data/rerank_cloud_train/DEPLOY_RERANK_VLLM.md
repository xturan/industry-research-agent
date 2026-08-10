# 部署推荐 reranker（v6 clean-OPD LoRA）到 vLLM

交接文档：`RERANK_TRAINING_HANDOFF.md`。推荐版本：

```text
output/rerank_3b_lora_v6_opd_clean/checkpoint-120
```

基座：`Qwen/Qwen2.5-3B-Instruct`。

## 0. 权重现状（重要）

推荐 checkpoint 已同步到仓库内：

```text
data/rerank_cloud_train/output/rerank_3b_lora_v6_opd_clean/checkpoint-120/
  adapter_model.safetensors   ~114 MB（float32，504 个 LoRA 张量，已校验完整）
  adapter_config.json         peft_type=LORA, r=16, alpha=32, base=Qwen/Qwen2.5-3B-Instruct
  tokenizer.json / tokenizer_config.json / chat_template.jinja
  base_model_name.txt / train_meta.json
```

> 注意：`data/rerank_cloud_train/rerank_3b_lora_v6_opd_clean/`（顶层）里还有一份 **0 字节** 的
> `adapter_model.safetensors` 残留，别用那份；部署只用 `output/rerank_3b_lora_v6_opd_clean/checkpoint-120/`。

若换到另一台 GPU 机器部署，把整个 `checkpoint-120/` 目录带上即可。

## 1. 起 vLLM 服务

在 GPU 机器（Linux，2×RTX 4090 验证过）上：

```bash
export CHECKPOINT_DIR=/path/to/output/rerank_3b_lora_v6_opd_clean/checkpoint-120
bash data/rerank_cloud_train/deploy_rerank_v6_vllm.sh
```

等价命令：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-3B-Instruct \
  --enable-lora \
  --max-lora-rank 16 \
  --lora-modules rerank-lora=/path/to/output/rerank_3b_lora_v6_opd_clean/checkpoint-120 \
  --served-model-name Qwen/Qwen2.5-3B-Instruct \
  --port 8000 \
  --max-model-len 1536
```

> `--lora-modules <name>=<path>` 的 `<name>` 必须和应用的 `RERANK_MODEL` 一致（默认 `rerank-lora`）。
> 如果 GPU 显存有限，可追加 `--gpu-memory-utilization 0.6`；本机曾用 AWQ 基座（见 `scripts/_start_rerank.sh`），
> 若手头只有 AWQ 量化基座，把 `--model` 换成 AWQ 路径并加 `--quantization awq`，LoRA 仍按此方式挂载。

## 1b. 本机启动（RTX 5060 8GB / WSL）

本机 WSL 里只有 **AWQ 3B 基座缓存**（`/home/hjz/models/Qwen2.5-3B-Instruct-AWQ`，vllm 0.26.0，8GB 显存），
没有 BF16 基座。因此走 **AWQ 基座 + LoRA 补丁 base** 路线（与既有 `_start_rerank.sh` / `_deploy_rerank_lora.sh` 同款模式），
脚本 `scripts/_start_rerank_v6.sh` 已封装：把 v6 adapter 复制到 `/home/hjz/rerank-lora-adapter-v6`、
把 `adapter_config.json` 的 `base_model_name_or_path` 补丁成 AWQ id，再用 `--lora-modules rerank-lora=<DST>` 起服务。

在 WSL 里执行：

```bash
bash /mnt/e/invest_agent/scripts/_start_rerank_v6.sh
```

启动后本机可直接访问 `http://localhost:8000/v1/chat/completions`（WSL2 自动转发 localhost），
`.env` 用默认 `RERANK_ENDPOINT` 即可，无需改。

> 若想改用 BF16 基座（无需补丁 base），先让 vLLM 下载 `Qwen/Qwen2.5-3B-Instruct`（约 6GB，需 WSL 联网），
> 再跑 `bash data/rerank_cloud_train/deploy_rerank_v6_vllm.sh`；8GB 显存较紧，建议同时加 `--gpu-memory-utilization 0.9`。

## 2. 应用侧配置（invest-agent）

在 `.env` 中设置：

```dotenv
RERANK_ENDPOINT=http://<host>:8000/v1/chat/completions
RERANK_MODEL=rerank-lora
```

代码读取点：`packages/rag/rerankers.py::rerank_with_llm`（`rerankers.py` 顶部注释的部署示例）。
默认 `RERANK_ENDPOINT=http://localhost:8000/v1/chat/completions` 适用于本机部署。

## 3. 验证

**curl 冒烟**（POST 一个 prompt，应返回 `logprobs.content[0].top_logprobs` 里含 0-4 digit）：

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "rerank-lora",
    "messages": [{"role": "user", "content": "### Instruction:\n你是一个产业研究检索精排器。判断下面文档对查询的相关性，输出 0-4 五档分数：0=无关，1=弱相关，2=一般相关，3=相关且有实质信息，4=核心证据。只输出一个数字。\n\n### Input:\n查询：湖南浏阳烟花产业\n\n文档：2023年浏阳烟花产值突破500亿元。\n\n### Response:\n"}],
    "max_tokens": 1,
    "temperature": 0.0,
    "logprobs": true,
    "top_logprobs": 8
  }'
```

**跑现有检索排序评估**（模型未起会自动降级到 deterministic，不会崩）：

```bash
python scripts/eval_retrieval_ranking_v1.py
```

**跑单测**：

```bash
python -m pytest tests/test_rerankers.py tests/test_retrieval_rank.py -q
```

## 4. 接入点说明

- `packages/rag/rerankers.py::rerank_with_llm` —— 推理协议（v6 handoff）：
  精确 prompt 模板（`### Instruction / ### Input / ### Response`）、`max_tokens=1`、
  请求 `logprobs` 计算 `expected_score = sum(prob[i]*i)`，映射为 0..1 分数（`expected_score/4`）。
  服务拒绝 `logprobs` 参数或 4xx 时自动降级为文本正则解析；请求异常时返回中性分 0.5。
- `packages/research_harness/retrieval_rank.py::rerank_chunks_llm` —— 全部 0.5（模型实际不可用）时
  走 `deterministic_fallback`（chunk quality + coarse score），不阻塞主流程。
- `packages/research_harness/retrieval_bridge.py::build_graph_retrieval_artifacts` —— graph-runtime 路径已接入
  `rank_retrieved_sources`，产出精排后的 `source_chunks` 与 `retrieval_pack.rerank_mode`。

## 5. 不建议接入

`rerank_3b_lora_v7_hard_opd` / `checkpoint-40`（hard-mining 回退，exact/nDCG/4 类召回均下降）。
