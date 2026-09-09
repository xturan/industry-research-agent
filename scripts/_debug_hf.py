import os
import socket

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
print("socket family test:", socket.getaddrinfo("hf-mirror.com", 443)[:2])

import requests

r = requests.get("https://hf-mirror.com/BAAI/bge-m3/resolve/main/config.json", timeout=20)
print("requests hf-mirror:", r.status_code, len(r.content))

from huggingface_hub import hf_hub_download

try:
    p = hf_hub_download("BAAI/bge-m3", "config.json")
    print("hf_hub_download ok:", p)
except Exception as exc:
    print("hf_hub_download FAIL:", type(exc).__name__, str(exc)[:400])
