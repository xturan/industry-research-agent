#!/usr/bin/env bash
for u in "https://huggingface.co" "https://hf-mirror.com" "https://www.modelscope.cn" "https://pypi.tuna.tsinghua.edu.cn" "https://www.baidu.com"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$u" 2>/dev/null)
  echo "$u -> ${code:-TIMEOUT/ERR}"
done
