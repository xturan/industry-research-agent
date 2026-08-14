#!/usr/bin/env bash
echo "=== search DeepSeek-R1-Distill-Qwen-7B AWQ/GPTQ ==="
curl -sL --max-time 20 "https://huggingface.co/api/models?search=DeepSeek-R1-Distill-Qwen-7B-AWQ&limit=10" -o /tmp/s1.json
python3 -c "import json; d=json.load(open('/tmp/s1.json')); print('\n'.join(m.get('id','') for m in d if isinstance(m,dict)))" 2>/dev/null
echo "=== search DeepSeek-R1-Distill-Qwen-7B GPTQ ==="
curl -sL --max-time 20 "https://huggingface.co/api/models?search=DeepSeek-R1-Distill-Qwen-7B-GPTQ&limit=10" -o /tmp/s2.json
python3 -c "import json; d=json.load(open('/tmp/s2.json')); print('\n'.join(m.get('id','') for m in d if isinstance(m,dict)))" 2>/dev/null
echo "=== Qwen2.5-7B-Instruct-AWQ ==="
code=$(curl -s -o /tmp/s3.json -w "%{http_code}" --max-time 15 -L "https://huggingface.co/api/models/Qwen/Qwen2.5-7B-Instruct-AWQ")
echo "http: ${code}"
if [ "${code}" = "200" ]; then python3 -c "import json; d=json.load(open('/tmp/s3.json')); print('siblings:', len(d.get('siblings',[])))"; fi
