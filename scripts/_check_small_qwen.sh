#!/usr/bin/env bash
for r in \
  "Qwen/Qwen2.5-3B-Instruct-AWQ" \
  "Qwen/Qwen2.5-1.5B-Instruct-AWQ" \
  "Qwen/Qwen2.5-0.5B-Instruct" \
  "Qwen/Qwen3-4B-Instruct-2507" \
  "Qwen/Qwen2.5-3B-Instruct" \
  "Qwen/Qwen2.5-1.5B-Instruct"; do
  code=$(curl -s -o /tmp/smallq.json -w "%{http_code}" --max-time 15 -L "https://huggingface.co/api/models/${r}")
  if [ "${code}" = "200" ]; then
    n=$(python3 -c "import json; d=json.load(open('/tmp/smallq.json')); print(len(d.get('siblings',[])))")
    echo "${r} -> OK (${n} files)"
  else
    echo "${r} -> ${code}"
  fi
done
