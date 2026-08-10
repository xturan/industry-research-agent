#!/usr/bin/env bash
Z="$HOME/vllm-env/lib/python3.12/site-packages/ziglang/zig"
cat > /tmp/link_probe.c <<'EOF'
typedef int CUresult;
extern CUresult cuInit(unsigned int flags);
int probe(void) { return (int)cuInit(0); }
EOF
echo "--- -l:libcuda.so.1 ---"
"$Z" cc -shared -fPIC /tmp/link_probe.c -o /tmp/p1.so -l:libcuda.so.1 -L/usr/lib/wsl/lib 2>&1 | head -4
echo "exit ${PIPESTATUS[0]}"
echo "--- -lcuda ---"
"$Z" cc -shared -fPIC /tmp/link_probe.c -o /tmp/p2.so -lcuda -L/usr/lib/wsl/lib 2>&1 | head -4
echo "exit ${PIPESTATUS[0]}"
ls -l /tmp/p2.so 2>/dev/null
