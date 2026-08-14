#!/usr/bin/env bash
ZIG="$HOME/vllm-env/lib/python3.12/site-packages/ziglang/zig"
echo "zig path: $ZIG"
ls -la "$ZIG" 2>&1 | head -3
"$ZIG" version 2>&1 | head -2
echo "int f(void){return 42;}" > /tmp/t.c
"$ZIG" cc -O3 -shared -fPIC -Wno-psabi -o /tmp/t.so /tmp/t.c 2>&1 | head -5
echo "exit: $?"
ls -l /tmp/t.so 2>&1
