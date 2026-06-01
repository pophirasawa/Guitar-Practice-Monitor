import json
import random
from datetime import date, timedelta
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "data" / "practice_log.json"
path.parent.mkdir(exist_ok=True)
try:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
except Exception:
    data = {}

topics = [
    "哈农、C 大调音阶、左手琶音",
    "和弦转位、节奏稳定性",
    "慢练右手旋律，分手合手",
    "视奏 20 分钟，复习旧曲",
    "踏板控制和弱音练习",
    "音阶循环、属七和弦连接",
]

random.seed(20260529)
today = date.today()
for offset in range(1, 130):
    day = today - timedelta(days=offset)
    if random.random() < 0.24:
        continue
    seconds = random.randint(18 * 60, 115 * 60)
    if random.random() < 0.08:
        seconds += random.randint(60 * 60, 180 * 60)
    key = day.isoformat()
    existing = data.get(key)
    if isinstance(existing, dict):
        existing.setdefault("seconds", seconds)
        existing.setdefault("note", random.choice(topics))
    else:
        data[key] = {"seconds": seconds, "note": random.choice(topics)}

path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"seeded {path}")
