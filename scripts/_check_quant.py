"""Introspect installed vLLM for supported quantization methods & LoRA support."""
from vllm.model_executor.layers.quantization import get_quantization_config, QUANTIZATION_METHODS

print("QUANTIZATION_METHODS:", QUANTIZATION_METHODS)
for name in sorted(QUANTIZATION_METHODS):
    if any(k in name.lower() for k in ("bits", "bnb", "awq", "gptq", "fp8", "gguf")):
        print("  relevant:", name)
