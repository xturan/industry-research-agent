import pathlib
path = pathlib.Path("packages/research_reports/dossier.py")
content = path.read_text(encoding="utf-8")

# Legacy dossier header
content = content.replace('"# Deep Research 运行档案\\n"', '"# Deep Research 运行档案\\n"')
content = content.replace('f"- Report ID:', 'f"- 报告 ID:')
content = content.replace('f"- Generated At:', 'f"- 生成时间:')
content = content.replace('f"- Original Query:', 'f"- 原始查询:')
content = content.replace('f"- Overall Confidence:', 'f"- 综合置信度:')
content = content.replace('f"- Search Rounds Executed:', 'f"- 搜索轮次:')
content = content.replace('f"- Estimated Tavily Credits:', 'f"- 预估积分:')
content = content.replace('"## 1. Query And Sources"', '"## 1. 查询与来源"')
content = content.replace('"## 2. Evidence And Agent Pipeline"', '"## 2. 证据与代理流水线"')
content = content.replace('"## 3. Content Assets And Generation Trace"', '"## 3. 内容资产与生成追踪"')

# Overview table
content = content.replace('f"| Node Count |', 'f"| 节点数 |')
content = content.replace('f"| Context Pack Count |', 'f"| 上下文包数 |')
content = content.replace('f"| Evidence Coverage |', 'f"| 证据覆盖率 |')
content = content.replace('f"| Citation Integrity |', 'f"| 引用完整性 |')
content = content.replace('f"| Source Quality |', 'f"| 来源质量 |')
content = content.replace('f"| Final Score |', 'f"| 综合评分 |')

# Remaining English after the earlier fix missed some
content = content.replace('"### 来源质量 V2\\n\\nNo Source Quality v2 records', '"### 来源质量 V2\\n\\n未捕获来源质量V2记录')

# Also fix table sub-headers
content = content.replace('f"| Credibility | Search Phrase | Title | URL | Text Retained |"',
                          'f"| 可信度 | 搜索短语 | 标题 | URL | 文本保留 |"')

# Check for remaining "No ... captured" patterns
import re
remaining = re.findall(r'No [A-Za-z].*?captured', content)
if remaining:
    print(f"WARNING: remaining English patterns: {remaining}")

path.write_text(content, encoding="utf-8")
print(f"Done. {len(content)} chars")
