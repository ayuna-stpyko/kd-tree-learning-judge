"""順位表。スコア (スコア用ケースの実行時間の和) の昇順、同じなら提出が早い方が上。

view=best: 1 人 1 行 (各自の最良記録)
view=all : AC した提出すべて
"""
import html
import time

from .common import HIDDEN_NAME_PREFIX, SCORE, SHORT_DATETIME_FMT, fmt_time, load_result

BEST, ALL = "best", "all"
VIEWS = {BEST: "各人のベスト", ALL: "すべての AC"}
REFRESH_SEC = 30
MEDAL_RANKS = 3  # 上位何位まで色を付けるか


def rows(db, view):
    counts = db.counts_by_name()
    out = []
    seen = set()
    for r in db.accepted():  # score, created_at の昇順
        if r["name"].startswith(HIDDEN_NAME_PREFIX):
            continue
        if view == BEST:
            if r["name"] in seen:
                continue
            seen.add(r["name"])
        out.append({
            "rank": len(out) + 1,
            "id": r["id"],
            "name": r["name"],
            "score": r["score"],
            "submitted_at": fmt_time(r["created_at"], SHORT_DATETIME_FMT),
            "submissions": counts.get(r["name"], 0),
            "times": {int(k): v for k, v in (load_result(r).get("score_times") or {}).items()},
        })
    return out


CSS = """
:root { --bg:#ffffff; --fg:#1f2328; --muted:#656d76; --line:#d0d7de; --head:#f6f8fa;
        --accent:#0969da; --gold:#bf8700; --silver:#6e7781; --bronze:#a0522d; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#8d96a0; --line:#30363d; --head:#161b22;
          --accent:#4493f8; --gold:#e3b341; --silver:#b1bac4; --bronze:#d18b5c; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", sans-serif; }
main { max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 4px; }
.sub { color: var(--muted); font-size: 13px; margin-bottom: 16px; }
.tabs { display:flex; gap:4px; border-bottom:1px solid var(--line); margin-bottom: 12px; }
.tabs a { padding: 8px 14px; text-decoration:none; color:var(--muted); border-bottom: 2px solid transparent; }
.tabs a.on { color: var(--fg); border-bottom-color: var(--accent); font-weight: 600; }
.wrap { overflow-x: auto; }
table { width:100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
th { background: var(--head); font-weight: 600; font-size: 12px; color: var(--muted); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.rank { font-weight: 700; width: 3em; }
tr.r1 td.rank { color: var(--gold); } tr.r2 td.rank { color: var(--silver); } tr.r3 td.rank { color: var(--bronze); }
td.score { font-weight: 600; }
details summary { cursor: pointer; color: var(--accent); font-size: 12px; }
.dims { display:grid; grid-template-columns: repeat(5, auto); gap: 2px 12px; margin-top: 6px;
        font-size: 12px; font-variant-numeric: tabular-nums; color: var(--muted); }
.empty { color: var(--muted); padding: 24px 0; }
"""


def _detail(r):
    dims = "".join("<span>d=%d: %.3f</span>" % (d, t) for d, t in sorted(r["times"].items()))
    return '<details><summary>次元ごと</summary><div class="dims">%s</div></details>' % dims


# 表示する列: (見出し, セルの class, セルの中身)
_RANK = ("順位", "rank", lambda r: str(r["rank"]))
_NAME = ("名前", "", lambda r: html.escape(r["name"]))
_ID = ("提出 ID", "num", lambda r: str(r["id"]))
_SCORE = ("スコア (秒)", "num score", lambda r: "%.3f" % r["score"])
_DETAIL = ("内訳", "", _detail)
_TIME = ("提出時刻", "", lambda r: r["submitted_at"])
_COUNT = ("提出回数", "num", lambda r: str(r["submissions"]))
COLUMNS = {
    BEST: [_RANK, _NAME, _SCORE, _DETAIL, _TIME, _COUNT],
    ALL: [_RANK, _NAME, _ID, _SCORE, _DETAIL, _TIME],
}


def render(cfg, data, view):
    cols = COLUMNS[view]
    tabs = "".join('<a href="/?view=%s" class="%s">%s</a>' % (v, "on" if v == view else "", label)
                   for v, label in VIEWS.items())
    head = "".join('<th class="%s">%s</th>' % (cls, title) for title, cls, _ in cols)
    body = "".join(
        '<tr class="%s">%s</tr>' % ("r%d" % r["rank"] if r["rank"] <= MEDAL_RANKS else "",
                                    "".join('<td class="%s">%s</td>' % (cls, cell(r)) for _, cls, cell in cols))
        for r in data)
    table = ('<div class="wrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, body)
             if data else '<p class="empty">まだ AC した提出はありません。</p>')
    dims = sorted(c["d"] for c in cfg.problem.cases if c["phase"] == SCORE)
    return """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="%(refresh)d">
<title>kd-tree 順位表</title><style>%(css)s</style></head>
<body><main>
<h1>%(title)s 順位表</h1>
<div class="sub">スコア = スコア用ケース (d=%(dmin)d〜%(dmax)d) の実行時間の和。小さいほど上位。%(refresh)d 秒ごとに自動更新 (最終更新 %(now)s)</div>
<nav class="tabs">%(tabs)s</nav>
%(table)s
</main></body></html>
""" % {"refresh": REFRESH_SEC, "css": CSS, "title": html.escape(cfg.problem.title), "dmin": dims[0],
       "dmax": dims[-1], "now": time.strftime("%H:%M:%S"), "tabs": tabs, "table": table}
