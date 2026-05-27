import json, sys, os
from datetime import datetime, timezone
from pathlib import Path
H = os.path.expanduser("~")
SIGNAL = Path(H) / ".claude" / "session-env" / "memory_touched.txt"
try: UTC = datetime.UTC
except AttributeError: UTC = timezone.utc
def main():
    try: payload = json.loads(sys.stdin.read())
    except: return 0
    ti = payload.get("tool_input", {}) or {}
    fp = ti.get("file_path", "") if isinstance(ti, dict) else ""
    if not fp: return 0
    fl = fp.replace(chr(92), "/").lower()
    if "/tmp/" in fl or "/data/" in fl: return 0
    ok = any(fp.endswith(e) for e in (".py", ".md", ".json", ".toml", ".html"))
    if not ok: return 0
    SIGNAL.parent.mkdir(parents=True, exist_ok=True)
    SIGNAL.write_text(datetime.now(UTC).isoformat() + chr(9) + fp + chr(10), encoding="utf-8")
    return 0
if __name__ == "__main__": sys.exit(main())
