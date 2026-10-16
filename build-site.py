"""生成网站用的数据：data.json（兼容旧客户端）+ index.json + 分片 p/。

复用 build-client.py 里的精简与分类逻辑，保证网站和插件面板看到的是同一份数据、
同一套分类，不会出现两边不一致。

为什么要分片：清单有 4 MB，浏览器一次性拉完要几十秒（经 Cloudflare 时更久，
实测 1–20 KB/s 且时常断流）。分片后首屏只需要「索引 + 第一片」几十 KB。
服务器上是 dsh_index/site.py 在做同一件事，**格式必须与它保持一致**。
"""

import importlib.util
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
# 与服务器 dsh_index/site.py 的 PAGE_SIZE 保持一致
PAGE_SIZE = 500

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

site_dir = BASE / "site"
site_dir.mkdir(parents=True, exist_ok=True)

# 1) 全量文件：留给已安装的旧版插件和旧页面，不再被新版消费
target = site_dir / "data.json"
target.write_text(
    json.dumps(out, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)

# 2) 分片：片名带生成戳，内容不可变，因此可以长缓存
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
shard_dir = site_dir / "p"
shard_dir.mkdir(parents=True, exist_ok=True)
for stale in shard_dir.glob("*.json"):
    if not stale.name.startswith(stamp):
        stale.unlink()

pages = []
for i in range(0, len(plugins), PAGE_SIZE):
    chunk = plugins[i:i + PAGE_SIZE]
    name = f"{stamp}-{i // PAGE_SIZE + 1}.json"
    (shard_dir / name).write_text(
        json.dumps(chunk, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    pages.append({"f": f"p/{name}", "n": len(chunk)})

dist: dict = {}
for item in plugins:
    dist[item["g"]] = dist.get(item["g"], 0) + 1

# 3) 索引：首屏只取它，所以统计量都放在这里
index = {
    "generated_at": out["generated_at"],
    "counts_total": out["counts_total"],
    "order": out["order"],
    "page_size": PAGE_SIZE,
    "pages": pages,
    "categories": dist,
    "hot_50": sum(1 for p in plugins if (p.get("st") or 0) >= 50),
    "pinned": sum(1 for p in plugins if p.get("k") in ("npm", "tag", "commit")),
}
index_path = site_dir / "index.json"
index_path.write_text(
    json.dumps(index, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)

print(f"entries : {len(plugins)}")
print(f"output  : {index_path}")
print(f"          {shard_dir}（{len(pages)} 片 × {PAGE_SIZE} 条）")
print(f"size    : 索引 {index_path.stat().st_size / 1024:.1f} KiB，"
      f"data.json {target.stat().st_size / 1024 / 1024:.1f} MiB（旧客户端用）")
