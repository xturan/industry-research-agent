#!/usr/bin/env bash
TRI=~/vllm-env/lib/python3.12/site-packages/triton
SRC="$TRI/backends/nvidia/driver.c"
OUT=/tmp/driver_test.so
rm -f "$OUT"
/home/hjz/bin/cc "$SRC" -O3 -shared -fPIC -Wno-psabi \
  -o "$OUT" \
  -l:libcuda.so.1 \
  -L"$TRI/backends/nvidia/lib" \
  -L/usr/lib/wsl/lib \
  -I"$TRI/backends/nvidia/include" \
  -I/tmp \
  -I/usr/include/python3.12 2>&1 | head -25
echo "exit: ${PIPESTATUS[0]}"
ls -l "$OUT" 2>/dev/null
