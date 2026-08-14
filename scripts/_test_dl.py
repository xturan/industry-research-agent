import os
import time

os.environ["HF_HUB_DISABLE_XET"] = "1"
from huggingface_hub import hf_hub_download

start = time.time()
# Download a reasonably large file from bge-m3 (pytorch_model.bin is 2.1GB).
try:
    p = hf_hub_download(
        "BAAI/bge-m3",
        "pytorch_model.bin",
    )
    print("done in", round(time.time() - start, 1), "s ->", p)
except Exception as exc:
    print("FAIL:", type(exc).__name__, str(exc)[:300])
