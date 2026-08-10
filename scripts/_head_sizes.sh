#!/usr/bin/env bash
TOKEN="hf_XXX_PUT_YOUR_TOKEN_HERE"
for f in model-00001-of-00002.safetensors model-00002-of-00002.safetensors tokenizer.json vocab.json merges.txt; do
  len=$(curl -sI -L --max-time 20 -H "Authorization: Bearer ${TOKEN}" "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-AWQ/resolve/main/${f}" | tr -d '\r' | awk -F': ' 'tolower($1)=="content-length"{print $2}')
  echo "${f} -> ${len}"
done
