#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$HOME/bin"
cat > "$HOME/bin/cc" <<'EOF'
#!/usr/bin/env bash
# CC shim: forward to zig cc, translating GNU exact-filename link flags
# (-l:libX.so.N) that zig's lld does not accept into -lX.
args=()
for a in "$@"; do
  case "$a" in
    -l:lib*.so*)
      base=$(printf '%s' "${a#-l:lib}" | sed -E 's/\.so([.0-9]*)$//')
      a="-l${base}"
      ;;
  esac
  args+=("$a")
done
exec "$HOME/vllm-env/lib/python3.12/site-packages/ziglang/zig" cc "${args[@]}"
EOF
chmod +x "$HOME/bin/cc"
echo "updated $HOME/bin/cc"
# verify translation
cat > /tmp/link_probe.c <<'CEOF'
typedef int CUresult;
extern CUresult cuInit(unsigned int flags);
int probe(void) { return (int)cuInit(0); }
CEOF
"$HOME/bin/cc" -shared -fPIC /tmp/link_probe.c -o /tmp/p3.so -l:libcuda.so.1 -L/usr/lib/wsl/lib 2>&1 | head -3
echo "translate-link exit: ${PIPESTATUS[0]}"
ls -l /tmp/p3.so 2>/dev/null
