import json, sys
from datetime import datetime, timezone
from pathlib import Path
SIGNAL = Path(r"C:/Users/LEGION/.claude/session-env/last_session.json")
try: UTC = datetime.UTC
except AttributeError: UTC = timezone.utc
def main():
    try: payload = json.loads(sys.stdin.read())
    except: payload = {}
    entry = {"ended_at": datetime.now(UTC).isoformat(), "session_id": payload.get("session_id", "")}
    SIGNAL.parent.mkdir(parents=True, exist_ok=True)
    SIGNAL.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0
if __name__ == "__main__": sys.exit(main())
