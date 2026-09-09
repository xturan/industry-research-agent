"""Batch replace English strings with Chinese in dossier.py."""
import pathlib, re

path = pathlib.Path("packages/research_reports/dossier.py")
content = path.read_text(encoding="utf-8")

replacements = [
    # Subsection headers
    ("### Query Expansion", "### 查询扩展"),
    ("### Planner Contract", "### 规划合约"),
    ("### Search Rounds", "### 搜索轮次"),
    ("### Source Candidates", "### 来源候选"),
    ("### Source Assessments", "### 来源评估"),
    ("### Source Quality V2", "### 来源质量 V2"),
    ("### Source Quality v2", "### 来源质量 V2"),
    ("### Evidence Items", "### 证据条目"),
    ("### Claims", "### 研究断言"),
    ("### Agent Pipeline", "### 代理流水线"),
    ("### Context Packs", "### 上下文包"),
    ("### Tool Traces", "### 工具追踪"),
    ("### Human Review", "### 人工复核"),
    ("### Final Report", "### 最终报告"),
    ("### Sources", "### 来源"),
    ("### Search Events", "### 搜索事件"),
    ("### Evidence", "### 证据"),
    ("### Claim Support Matrix", "### 断言支撑矩阵"),
    ("### Claim Verifications", "### 断言验证"),
    ("### Contract Diagnostics", "### 合约诊断"),
    ("### Retrieval Pack", "### 检索包"),
    ("### Detailed Agent Trace", "### 代理追踪详情"),
    # Table headers
    ('"| Item | Value |"', '"| 指标 | 数值 |"'),
    ('"| Planner Item | Value |"', '"| 规划项 | 数值 |"'),
    ('"| Field | Value |"', '"| 字段 | 数值 |"'),
    # Misc labels
    ('"Context Pack Details"', '"上下文包详情"'),
    ('"Over-budget Context Packs"', '"超预算上下文包"'),
    ('"Graph Glossary"', '"术语说明"'),
    ('"Dossier Notes"', '"档案说明"'),
    ("LangGraph Research Run Dossier", "LangGraph 研报运行档案"),
    ("Deep Research Run Dossier", "Deep Research 运行档案"),
    # No ... captured patterns
    ('"No query expansion details were captured in V1.\\n"', '"未捕获查询扩展详情。\\n"'),
    ('"No planner contract details were captured.\\n"', '"未捕获规划合约详情。\\n"'),
    ('"No graph node steps were captured.\\n"', '"未捕获图节点步骤。\\n"'),
    ('"No search events were captured.\\n"', '"未捕获搜索事件。\\n"'),
    ('"No graph source objects were captured.\\n"', '"未捕获图来源对象。\\n"'),
    ('"No graph evidence objects were captured.\\n"', '"未捕获图证据对象。\\n"'),
    ('"No graph claim objects were captured.\\n"', '"未捕获图断言对象。\\n"'),
    ('"No claim support matrix records were captured.\\n"', '"未捕获断言支撑矩阵记录。\\n"'),
    ('"No claim verification records were captured.\\n"', '"未捕获断言验证记录。\\n"'),
    ('"No contract diagnostics were captured.\\n"', '"未捕获合约诊断。\\n"'),
    ('"No context packs were captured.\\n"', '"未捕获上下文包。\\n"'),
    ('"No tool traces were captured.\\n"', '"未捕获工具追踪。\\n"'),
    ('"No dimension_plan entries were captured.\\n"', '"未捕获维度计划条目。\\n"'),
    ('"No search round details were captured in V1.\\n"', '"未捕获搜索轮次详情。\\n"'),
    ('"No Source Quality v2 records were captured.\\n"', '"未捕获来源质量V2记录。\\n"'),
    ('"No detailed trace events were captured.\\n"', '"未捕获追踪事件详情。\\n"'),
    ('"No retrieval focus rows were captured.\\n\\n"', '"未捕获检索焦点行。\\n\\n"'),
    # Dossier notes
    ("V2 records visible inputs, outputs, source decisions, evidence, and agent-stage summaries. It does not store raw hidden model reasoning.",
     "V2记录可见的输入、输出、来源决策、证据和代理阶段摘要。不存储隐藏的模型推理。"),
    ("Sensitive fields such as API keys, authorization headers, tokens, and reasoning are excluded.",
     "敏感字段如API密钥、授权头、令牌和推理内容已排除。"),
    # Table column headers
    ('"| Type | ID | Name | Families | Terms"', '"| 类型 | ID | 名称 | 源族 | 口径词"'),
    ('"| Dimension | Description | Caliber Terms | Source Priority |"', '"| 维度 | 描述 | 口径词 | 来源优先级 |"'),
    ('"| Coverage Required | Expected Section | Source Families |"', '"| 覆盖要求 | 预期章节 | 源族 |"'),
]

for old, new in replacements:
    content = content.replace(old, new)

path.write_text(content, encoding="utf-8")
print(f"Done. {len(content)} chars written.")
