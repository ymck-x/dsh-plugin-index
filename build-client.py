"""把服务器产出的清单压成浏览器插件能直接用的 client.js。

为什么走「内联」而不是让 Host 半读文件 + 注册路由：
  清单是构建期产物、纯静态数据，Host 侧中转要跨 Cordis 的服务注入、
  HTTP 路由注册、同源校验三道门，任何一道没接好就是「取不到数据」。
  直接内联进 client.js 之后，插件零网络、零注入、零路由依赖，
  浏览器刷新即生效，也不需要重启 DSH。

用法：
    python build-client.py            # 读 data/plugins.json，写 lib/client.js
    python build-client.py --limit 5000
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "data" / "plugins.json"
OUT = BASE / "lib" / "client.js"

# 短键名：9486 条全字段会给浏览器多塞几 MB，这里只留界面真正要显示的
FIELDS = (
    ("r", "repo"),
    ("s", "install_spec"),
    ("n", "package_name"),
    ("v", "version"),
    ("d", "description"),
    ("c", "has_client"),
    ("k", "spec_kind"),
    ("e", "evidence_score"),
    # 星数只用于排序和「只看 N 星以上」筛选，不作为质量结论
    ("st", "stars"),
)

DESC_MAX = 110

# 功能分类：纯关键词规则，不调模型（零成本、可复现、改规则即刻生效）。
# 顺序即优先级 —— 先匹配到的类别胜出，所以特征最强的放前面。
# 匹配范围是 description + keywords + 包名 + 仓库名。
CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    # 特征最强的排前面，宽泛的（ui / 界面）排后面，避免抢词
    ("用量与计费", ("balance", "usage", "cost", "billing", "token", "余额", "用量", "计费",
                "消耗", "价格", "计费", "统计面板")),
    ("模型接入", ("connect-", "subscription", "provider", "api-key", "apikey", "接入", "订阅",
                "openai", "claude", "gemini", "kimi", "grok", "glm", "qwen", "codex",
                "account-pool", "shared-pool", "model")),
    ("记忆与上下文", ("memory", "recall", "context", "brain", "remember", "记忆", "上下文", "knowledge")),
    ("多智能体", ("multi-agent", "subagent", "orchestrat", "teams", "swarm", "团队", "多智能体", "协作")),
    ("会话与工作区", ("session", "workspace", "branch", "turn", "conversation", "handoff",
                "会话", "工作区", "分支", "轮次")),
    ("通讯与集成", ("discord", "feishu", "dingtalk", "wecom", "slack", "telegram", "bridge",
                "connector", "mcp", "webhook", "messaging", "gateway", "机器人", "通知", "集成")),
    ("搜索与抓取", ("search", "fetch", "crawl", "scrape", "searxng", "tavily", "exa", "搜索", "爬")),
    ("文档与办公", ("ppt", "pptx", "excel", "word", "office", "docx", "novel", "thesis",
                "markdown", "pdf", "文档", "写作", "论文")),
    ("开发工具", ("lint", "test", "review", "git", "todo", "debug", "refactor", "工程", "审查", "测试")),
    ("技能与提示词", ("skill", "prompt", "persona", "preset", "workflow", "技能", "提示词", "预设")),
    ("系统与运维", ("vps", "monitor", "restart", "backup", "deploy", "ssh", "terminal", "运维", "监控")),
    ("媒体与生成", ("image", "vision", "video", "audio", "voice", "tts", "speech", "图像", "语音", "视频", "绘图")),
    ("界面与显示", ("display", "layout", "render", "explorer", "sidebar", "menu", "dragndrop",
                "ui-", "-ui", "skin", "theme", "wallpaper", "live2d", "appearance",
                "显示", "布局", "外观", "壁纸", "皮肤", "菜单")),
    ("娱乐", ("game", "arcade", "pet", "游戏", "娱乐", "街机")),
]

OTHER = "其他"


def classify(plugin: dict) -> str:
    parts = [
        str(plugin.get("description") or ""),
        " ".join(plugin.get("keywords") or []),
        str(plugin.get("package_name") or ""),
        str(plugin.get("repo") or ""),
    ]
    haystack = " ".join(parts).lower()
    for name, keys in CATEGORIES:
        for key in keys:
            if key in haystack:
                return name
    return OTHER


def slim(plugin: dict) -> dict:
    out = {}
    for short, full in FIELDS:
        value = plugin.get(full)
        if full == "description":
            value = (value or "")[:DESC_MAX]
        elif full == "has_client":
            value = 1 if value else 0
        if value not in (None, "", 0):
            out[short] = value
    # has_client 是 0/1，0 也有意义（无界面），上面会被滤掉，这里补回
    out["c"] = 1 if plugin.get("has_client") else 0
    out["g"] = classify(plugin)
    return out


TEMPLATE = """// 本文件由 build-client.py 生成，请勿手工编辑。
// 数据来源：服务器 dsh-index 管道产出的 public/plugins.json
// 生成时间：%(generated)s   条目数：%(count)d
//
// 清单直接内联在下面，所以这个插件不依赖网络、不依赖 Host 侧路由，
// 浏览器刷新即可生效。
window.__ModuleLoader__.load({
  id: 'dsh-plugin-index',
  factory: (require) => {
    const React = require('react');
    const { useState, useMemo } = React;
    const h = React.createElement;

    const META = %(meta)s;
    const PLUGINS = %(plugins)s;

    // 全部使用 DSH 的真实主题令牌（--dsw-alias-*，来自 cordis_inspect_query 的 Theme）。
    // 不要自造变量名：写错了不报错，只会静默回退到硬编码颜色，
    // 表现就是暗色主题下满屏白底。
    const css = `
    .dpi{color:var(--dsw-alias-label-primary,inherit);font:14px/1.6 system-ui,sans-serif;min-width:0;max-width:1140px;margin:0 auto;padding:8px}
    .dpi *{box-sizing:border-box}
    .dpi h2{font-size:22px;margin:0;color:var(--dsw-alias-label-primary,inherit)}
    .dpi .muted{color:var(--dsw-alias-label-secondary,inherit);opacity:.75;font-size:13px}
    .dpi a{color:var(--dsw-alias-brand-primary,inherit);text-decoration:none}
    .dpi a:hover{text-decoration:underline}
    .dpi .bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0}
    .dpi input[type=search]{font:inherit;color:var(--dsw-alias-label-primary,inherit);flex:1 1 240px;min-width:0;background:var(--dsw-alias-bg-base,transparent);border:1px solid var(--dsw-alias-border-l1,currentColor);border-radius:8px;padding:8px 10px}
    .dpi input[type=search]::placeholder{color:var(--dsw-alias-label-secondary,inherit);opacity:.6}
    .dpi select{font:inherit;color:var(--dsw-alias-label-primary,inherit);background:var(--dsw-alias-bg-layer-1,transparent);border:1px solid var(--dsw-alias-border-l1,currentColor);border-radius:8px;padding:8px 10px;cursor:pointer}
    .dpi button{font:inherit;border:1px solid var(--dsw-alias-border-l1,currentColor);border-radius:9px;background:var(--dsw-alias-bg-layer-1,transparent);color:var(--dsw-alias-label-primary,inherit);padding:6px 12px;cursor:pointer;white-space:nowrap}
    .dpi button:hover{border-color:var(--dsw-alias-border-l2,currentColor)}
    /* 不用实心填充：品牌色在亮/暗主题下的明暗不确定，
       填色再配白字会在浅品牌色上变成白底白字。
       描边 + 品牌色文字，在两种主题下都可见。 */
    .dpi button.primary{border-color:var(--dsw-alias-brand-primary,currentColor);color:var(--dsw-alias-brand-primary,inherit);font-weight:600}
    .dpi button.tab[aria-pressed=true]{border-color:var(--dsw-alias-brand-primary,currentColor);color:var(--dsw-alias-brand-primary,inherit);font-weight:600;background:var(--dsw-alias-bg-layer-2,transparent)}
    .dpi button:disabled{opacity:.5;cursor:default}
    .dpi .list{display:flex;flex-direction:column;gap:8px;margin-top:6px}
    .dpi .row{border:1px solid var(--dsw-alias-border-l1,currentColor);border-radius:12px;padding:12px;background:var(--dsw-alias-bg-layer-1,transparent);display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:start}
    .dpi .name{font-weight:600;color:var(--dsw-alias-label-primary,inherit);overflow-wrap:anywhere}
    .dpi .pkg{font-size:12px;color:var(--dsw-alias-label-secondary,inherit);opacity:.85;overflow-wrap:anywhere;margin-top:2px}
    .dpi .desc{margin:6px 0 0;color:var(--dsw-alias-label-secondary,inherit);overflow-wrap:anywhere}
    .dpi .tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
    .dpi .tag{font-size:12px;border-radius:6px;padding:1px 7px;background:var(--dsw-alias-bg-layer-2,transparent);color:var(--dsw-alias-label-secondary,inherit);border:1px solid var(--dsw-alias-border-l1,currentColor)}
    .dpi .tag.warn{color:var(--dsw-alias-state-warn-primary,inherit);border-color:var(--dsw-alias-state-warn-primary,currentColor)}
    .dpi .actions{display:flex;flex-direction:column;gap:6px;align-items:flex-end;min-width:112px}
    .dpi .status{font-size:12px;max-width:200px;text-align:right;color:var(--dsw-alias-label-secondary,inherit);overflow-wrap:anywhere}
    .dpi .status.error{color:var(--dsw-alias-state-error-primary,inherit)}
    .dpi .status.done{color:var(--dsw-alias-state-success-primary,inherit)}
    .dpi .notice{border-radius:9px;padding:10px 12px;margin:10px 0;background:var(--dsw-alias-bg-layer-2,transparent);color:var(--dsw-alias-label-primary,inherit)}
    .dpi .more{display:flex;justify-content:center;margin:14px 0}
    .dpi :focus-visible{outline:3px solid var(--dsw-alias-brand-primary,currentColor);outline-offset:2px}
    `;

    const PAGE = 60;
    // 网站版（同一份数据，静态托管，走 Cloudflare 隧道 → nginx:8081，与 DSH 隔离）
    const SITE_URL = 'https://cj.codexve.cn/';
    // 这三个地址类型是不可变的（内容不会随作者推代码而变），其余都跟随默认分支
    const PINNED = new Set(['npm', 'tag', 'commit']);
    const KIND_TEXT = { npm: 'npm 版本', tag: 'tag', commit: 'commit' };
    // 类别在构建期用关键词规则打好，这里按条目数降序（含「其他」）
    const GROUPS = (() => {
      const count = new Map();
      for (const p of PLUGINS) count.set(p.g || '其他', (count.get(p.g || '其他') || 0) + 1);
      return [...count.entries()].sort((a, b) => b[1] - a[1]).map((e) => e[0]);
    })();
    const FILTERS = [['all', '全部分类']].concat(GROUPS.map((g) => [g, g]));
    // 清单里存的是 owner/repo。主标题只放仓库名，owner 降为小字：
    // 仓库名会重复（清单里 dsh-plugins 就出现在 4 个不同 owner 下），
    // 所以 owner 不能完全不显示，只是不该顶在最前面。
    const repoName = (full) => String(full || '').split('/').pop() || String(full || '');
    const repoOwner = (full) => String(full || '').split('/')[0] || '';

    function Panel(props) {
      const [query, setQuery] = useState('');
      const [filter, setFilter] = useState('all');
      const [minStars, setMinStars] = useState(0);
      const [sort, setSort] = useState('default');
      const [limit, setLimit] = useState(PAGE);
      const [jobs, setJobs] = useState({});

      const shown = useMemo(() => {
        const q = query.trim().toLowerCase();
        let list = PLUGINS.filter((p) => {
          if (filter !== 'all' && p.g !== filter) return false;
          if (minStars > 0 && (p.st || 0) < minStars) return false;
          if (!q) return true;
          return [p.r, p.n, p.d].join(' ').toLowerCase().includes(q);
        });
        // 默认顺序是构建期的证据强度；按星数排是给「想看有人验证过的」用的
        if (sort === 'stars') {
          list = list.slice().sort((a, b) => (b.st || 0) - (a.st || 0));
        }
        return list;
      }, [query, filter, minStars, sort]);

      function setJob(repo, job) {
        setJobs((prev) => ({ ...prev, [repo]: job }));
      }

      async function install(p) {
        setJob(p.r, { state: 'installing', message: '正在安装…' });
        try {
          const value = await props.install(p.s);
          const application = value && value.application;
          let message = '已安装';
          if (application === 'restart-required') message = '已安装，需重启 DSH 生效';
          else if (application === 'overridden') message = '已安装，但被更高优先级覆盖';
          else if (application === 'failed') message = '安装完成但激活失败';
          setJob(p.r, { state: 'done', message });
        } catch (err) {
          setJob(p.r, { state: 'error', message: String((err && err.message) || err) });
        }
      }

      const head = h('div', null,
        h('h2', null, '插件索引'),
        h('p', { className: 'muted' },
          '共 ' + PLUGINS.length + ' 个经校验的插件 · 清单生成于 ' + (META.generated_at || '未知')),
        h('p', { className: 'muted' },
          '判定依据是 package.json 里的 dsh.bundle.patch，排序按证据强度而不是星数。'),
        // 网站是同一份数据的网页版，样式和筛选比设置页里这个面板宽松得多
        h('p', { className: 'muted' },
          '也可以在网站中浏览：',
          h('a', { href: SITE_URL, target: '_blank', rel: 'noopener noreferrer' }, SITE_URL))
      );

      const bar = h('div', { className: 'bar' },
        h('input', {
          type: 'search',
          placeholder: '搜索仓库、包名、描述',
          value: query,
          'aria-label': '搜索插件',
          onChange: (e) => { setQuery(e.target.value); setLimit(PAGE); },
        }),
        // 15 个类别做成按钮会占好几行，用下拉框一行放下且无歧义
        h('select', {
          value: filter,
          'aria-label': '按功能分类筛选',
          onChange: (e) => { setFilter(e.target.value); setLimit(PAGE); },
        },
          FILTERS.map(([key, label]) => h('option', { key, value: key }, label))
        ),
        h('select', {
          value: String(minStars),
          'aria-label': '按星数筛选',
          onChange: (e) => { setMinStars(Number(e.target.value)); setLimit(PAGE); },
        },
          [[0, '星数不限'], [10, '10 星以上'], [50, '50 星以上'], [200, '200 星以上']]
            .map(([value, label]) => h('option', { key: value, value: String(value) }, label))
        ),
        h('select', {
          value: sort,
          'aria-label': '排序方式',
          onChange: (e) => { setSort(e.target.value); setLimit(PAGE); },
        },
          [['default', '按证据强度'], ['stars', '按星数']]
            .map(([value, label]) => h('option', { key: value, value }, label))
        )
      );

      const rows = shown.slice(0, limit).map((p) => {
        const job = jobs[p.r];
        const tags = [];
        // 只在地址不固定时提醒 —— 固定地址是默认期望，不需要特意表扬
        if (!PINNED.has(p.k)) tags.push(h('span', { className: 'tag warn', key: 'k' }, '地址跟随分支'));

        return h('div', { className: 'row', key: p.r },
          h('div', null,
            h('div', { className: 'name', title: p.r }, repoName(p.r)),
            h('div', { className: 'pkg' },
              [repoOwner(p.r),
               (p.n || '') + (p.v ? ' @ ' + p.v : ''),
               // 0 星也照实显示 —— 清单里近三成是 0 星，藏起来只会让人误判
               (p.st || 0) + ' ★'].filter(Boolean).join(' · ')),
            p.d ? h('p', { className: 'desc' }, p.d) : null,
            tags.length ? h('div', { className: 'tags' }, tags) : null
          ),
          h('div', { className: 'actions' },
            h('button', {
              className: 'primary',
              disabled: Boolean(job && job.state === 'installing'),
              onClick: () => install(p),
            }, job && job.state === 'installing' ? '安装中…' : '安装'),
            job ? h('div', { className: 'status ' + (job.state || '') }, job.message) : null
          )
        );
      });

      return h('div', { className: 'dpi' },
        h('style', null, css),
        head,
        bar,
        h('p', { className: 'muted' }, '匹配 ' + shown.length + ' 个，显示前 ' + Math.min(limit, shown.length) + ' 个'),
        h('div', { className: 'list' }, rows),
        shown.length > limit
          ? h('div', { className: 'more' }, h('button', { onClick: () => setLimit(limit + PAGE) }, '再看 ' + PAGE + ' 个'))
          : null
      );
    }

    function apply(ctx) {
      ctx.slots.inject('settings.plugins.tab', () => ctx.slots.register({
        name: 'settings.plugins.tab',
        id: 'index',
        order: 20,
        label: () => '插件索引',
        inject: () => ({
          // DSH 已把 pluginManager 暴露成客户端 remote，直接调，不需要自建转发。
          install: async (spec) => {
            const result = await ctx.remote.pluginManager.installBundle(spec, { enabled: true });
            if (!result || result.ok !== true) {
              const failure = (result && result.error) || {};
              throw new Error(failure.message || failure.code || '安装失败');
            }
            return result.value;
          },
        }),
      }, Panel));
    }

    return { inject: ['slots', 'remote', 'remote.pluginManager'], apply };
  },
});
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只取前 N 条（0 = 全部）")
    args = ap.parse_args()

    with open(SRC, encoding="utf-8") as fh:
        payload = json.load(fh)

    plugins = payload.get("plugins") or []
    if args.limit:
        plugins = plugins[: args.limit]

    lite = [slim(p) for p in plugins]
    data_js = json.dumps(lite, ensure_ascii=False, separators=(",", ":"))
    # U+2028 / U+2029 在 JS 源码里会断行，必须转义
    data_js = data_js.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    meta = {
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "order": payload.get("order"),
    }

    text = TEMPLATE % {
        "generated": meta["generated_at"] or "",
        "count": len(lite),
        "meta": json.dumps(meta, ensure_ascii=False),
        "plugins": data_js,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)

    size = os.path.getsize(OUT)
    print(f"entries : {len(lite)}")
    print(f"output  : {OUT}")
    print(f"size    : {size} bytes ({size / 1024 / 1024:.1f} MiB)")

    # 类别分布：用来检查关键词规则的覆盖率，其他太多就说明规则要补
    dist: dict = {}
    for item in lite:
        dist[item["g"]] = dist.get(item["g"], 0) + 1
    total = len(lite) or 1
    print("")
    print("分类分布：")
    for name, n in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<12s} {n:>5d}  {100 * n / total:>5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
