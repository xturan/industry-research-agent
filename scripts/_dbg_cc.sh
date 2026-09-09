#!/usr/bin/env bash
SRC=$(find /tmp/tmptwpptti9 /tmp/tmp* -name "cuda_utils.c" 2>/dev/null | head -1)
echo "src: $SRC"
if [ -z "$SRC" ]; then
  # recreate a minimal cuda_utils.c probe
  SRC=/tmp/cuda_utils.c
  cat > "$SRC" <<'EOF'
#include <cuda_runtime.h>
#include <cuda.h>
#include <dlfcn.h>
EOF
fi
ls -la "$SRC"
/home/hjz/bin/cc "$SRC" -O3 -shared -fPIC -Wno-psabi \
  -o /tmp/cuda_utils_test.so \
  -l:libcuda.so.1 \
  -L/home/hjz/vllm-env/lib/python3.12/site-packages/triton/backends/nvidia/lib \
  -L/usr/lib/wsl/lib \
  -I/home/hjz/vllm-env/lib/python3.12/site-packages/triton/backends/nvidia/include \
  -I/tmp \
  -I/usr/include/python3.12 2>&1 | head -30
echo "exit: ${PIPESTATUS[0]}"
