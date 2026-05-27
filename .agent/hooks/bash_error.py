import json, sys
from datetime import datetime, timezone
from pathlib import Path
SIGNAL = Path(r'C:/Users/LEGION/.claude/session-env/last_error.json')
try: UTC = datetime.UTC
except AttributeError: UTC = timezone.utc
def main():
    try: payload = json.loads(sys.stdin.read())
    except: return 0
    tr = payload.get('tool_response', {}) or {}
    if isinstance(tr, dict) and tr.get('success', True): return 0
    ti = payload.get('tool_input', {}) or {}
    cmd = ti.get('command', '') if isinstance(ti, dict) else ''
    err = tr.get('error', '') or tr.get('stderr', '') if isinstance(tr, dict) else ''
    if not err: return 0
    entry = {'ts': datetime.now(UTC).isoformat(), 'cmd': cmd[:500], 'err': err[:2000]}
    SIGNAL.parent.mkdir(parents=True, exist_ok=True)
    SIGNAL.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0
if __name__ == '__main__': sys.exit(main())
