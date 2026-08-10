#!/usr/bin/env bash
for r in "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B-AWQ" "TheBloke/DeepSeek-R1-Distill-Qwen-7B-AWQ" "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"; do
  code=$(curl -s -o /tmp/rmeta.json -w "%{http_code}" --max-time 15 -L "https://huggingface.co/api/models/${r}")
  echo "${r} -> ${code}"
  if [ "${code}" = "200" ]; then
    python3 -c "import json; d=json.load(open('/tmp/rmeta.json')); print('  siblings:', len(d.get('siblings', []))); print('  first:', [s.get('rfilename') for s in d.get('siblings', [])][:5])"
  fi
done
