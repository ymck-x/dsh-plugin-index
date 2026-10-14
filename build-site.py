"""生成网站用的精简数据 site/data.json。

复用 build-client.py 里的精简与分类逻辑，保证网站和插件面板看到的是同一份数据、
同一套分类，不会出现两边不一致。
"""

import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("bc", BASE / "build-client.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

with open(BASE / "data" / "plugins.json", encoding="utf-8") as fh:
    payload = json.load(fh)

plugins = [mod.slim(p) for p in payload.get("plugins") or []]

out = {
    "generated_at": payload.get("generated_at"),
    "counts_total": (payload.get("counts") or {}).get("total"),
    "order": payload.get("order"),
    "plugins": plugins,
}

target = BASE / "site" / "data.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(out, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)

size = target.stat().st_size
print(f"entries : {len(plugins)}")
print(f"output  : {target}")
print(f"size    : {size} bytes ({size / 1024 / 1024:.1f} MiB)")
