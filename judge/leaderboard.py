"""順位表。スコア (スコア用ケースの実行時間の和) の昇順、同じなら提出が早い方が上。

view=best: 1 人 1 行 (各自の最良記録)
view=all : AC した提出すべて
"""
import html
import json
import time


def rows(db, view):
    acc = db.accepted()  # score, created_at の昇順
    counts = db.counts_by_name()
    out = []
    seen = set()
    for r in acc:
        if r["name"].startswith("_"):  # "_" で始まる名前 (動作確認用) は載せない
            continue
        if view == "best":
            if r["name"] in seen:
                continue
            seen.add(r["name"])
        res = json.loads(r["result"]) if r["result"] else {}
        out.append({
            "rank": len(out) + 1,
            "id": r["id"],
            "name": r["name"],
            "score": r["score"],
            "submitted_at": time.strftime("%m/%d %H:%M:%S", time.localtime(r["created_at"])),
            "submissions": counts.get(r["name"], 0),
            "times": {int(k): v for k, v in (res.get("score_times") or {}).items()},
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


def render(cfg, data, view):
    e = html.escape
    tabs = "".join(
        '<a href="/?view=%s" class="%s">%s</a>' % (v, "on" if v == view else "", label)
        for v, label in (("best", "各人のベスト"), ("all", "すべての AC"))
    )
    if view == "best":
        head = ('<th>順位</th><th>名前</th><th class="num">スコア (秒)</th><th>内訳</th>'
                '<th>提出時刻</th><th class="num">提出回数</th>')
    else:
        head = ('<th>順位</th><th>名前</th><th class="num">提出 ID</th><th class="num">スコア (秒)</th>'
                '<th>内訳</th><th>提出時刻</th>')
    body = []
    for r in data:
        dims = "".join('<span>d=%d: %.3f</span>' % (d, t) for d, t in sorted(r["times"].items()))
        detail = '<details><summary>次元ごと</summary><div class="dims">%s</div></details>' % dims
        cls = "r%d" % r["rank"] if r["rank"] <= 3 else ""
        if view == "best":
            body.append('<tr class="%s"><td class="rank">%d</td><td>%s</td><td class="num score">%.3f</td>'
                        '<td>%s</td><td>%s</td><td class="num">%d</td></tr>'
                        % (cls, r["rank"], e(r["name"]), r["score"], detail, r["submitted_at"], r["submissions"]))
        else:
            body.append('<tr class="%s"><td class="rank">%d</td><td>%s</td><td class="num">%d</td>'
                        '<td class="num score">%.3f</td><td>%s</td><td>%s</td></tr>'
                        % (cls, r["rank"], e(r["name"]), r["id"], r["score"], detail, r["submitted_at"]))
    table = ('<div class="wrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
             % (head, "".join(body))) if body else '<p class="empty">まだ AC した提出はありません。</p>'
    return """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>kd-tree 順位表</title><style>%s</style></head>
<body><main>
<h1>%s 順位表</h1>
<div class="sub">スコア = スコア用ケース (d=1〜10) の実行時間の和。小さいほど上位。30 秒ごとに自動更新 (最終更新 %s)</div>
<nav class="tabs">%s</nav>
%s
</main></body></html>
""" % (CSS, e(cfg.problem.title), time.strftime("%H:%M:%S"), tabs, table)
