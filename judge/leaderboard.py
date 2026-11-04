"""順位表。スコア (スコア用ケースの実行時間の和) の昇順、同じなら提出が早い方が上。

view=best: 1 人 1 行 (各自の最良記録)
view=all : AC した提出すべて
view=subs: 最近の提出と判定の状況

ページは POLL_SEC ごとに /api/board を取り直し、表を差し替える。新しい提出は右側にカードで出し、
判定が出たら結果を CARD_HOLD_SEC 秒表示してから引っ込める。
"""
import html
import json

from .common import (CORRECTNESS, HIDDEN_NAME_PREFIX, PHASE_NAMES, SCORE, SHORT_DATETIME_FMT, VERDICT_NAMES,
                     fmt_time, load_result)
from .db import DONE, QUEUED, RUNNING

BEST, ALL, SUBS = "best", "all", "subs"
VIEWS = {BEST: "各人のベスト", ALL: "すべての AC", SUBS: "提出状況"}
POLL_SEC = 2
CARD_HOLD_SEC = 10
RECENT_LIMIT = 50  # 提出状況に出す件数
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


def status_text(s):
    """待機中・判定中の提出の状況 (submit.py の表示と同じ言い方)。"""
    if s["status"] == QUEUED:
        ahead = s.get("queue_ahead", 0)
        return "待機中 (前に %d 件)" % ahead if ahead else "待機中"
    p = s.get("progress") or {}
    if p.get("phase") == CORRECTNESS:
        return "判定中 %s %d/%d" % (PHASE_NAMES[CORRECTNESS], p.get("done", 0), p.get("total", 0))
    if p.get("phase") == SCORE:
        return "判定中 %s d=%s" % (PHASE_NAMES[SCORE], p["d"]) if p.get("d") else "判定中 " + PHASE_NAMES[SCORE]
    return "判定中"


def submissions(db):
    """最近の提出 (新しい順)。判定済みの AC が本人の最良記録なら、その順位も付ける。"""
    best_rank = {r["id"]: r["rank"] for r in rows(db, BEST)}
    out = []
    for r in db.recent(RECENT_LIMIT, HIDDEN_NAME_PREFIX):
        if r["progress"]:
            r["progress"] = json.loads(r["progress"])
        s = {"id": r["id"], "name": r["name"], "status": r["status"],
             "submitted_at": fmt_time(r["created_at"], SHORT_DATETIME_FMT)}
        if r["status"] == DONE:
            s.update(verdict=r["verdict"], verdict_name=VERDICT_NAMES.get(r["verdict"], r["verdict"]),
                     score=r["score"], rank=best_rank.get(r["id"]))
        else:
            s["text"] = status_text(r)
        out.append(s)
    return out


CSS = """
:root { --bg:#ffffff; --fg:#1f2328; --muted:#656d76; --line:#d0d7de; --head:#f6f8fa; --card:#ffffff;
        --accent:#0969da; --gold:#bf8700; --silver:#6e7781; --bronze:#a0522d;
        --ac:#1a7f37; --ng:#cf222e; --wait:#9a6700; --flash:#fff8c5; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#8d96a0; --line:#30363d; --head:#161b22; --card:#161b22;
          --accent:#4493f8; --gold:#e3b341; --silver:#b1bac4; --bronze:#d18b5c;
          --ac:#3fb950; --ng:#f85149; --wait:#d29922; --flash:#3b2e00; }
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
tr.flash td { animation: flash 3s ease-out; }
@keyframes flash { from { background: var(--flash); } to { background: transparent; } }
.v-AC { color: var(--ac); font-weight: 700; } .v-ng { color: var(--ng); font-weight: 700; }
.v-wait { color: var(--wait); }
details summary { cursor: pointer; color: var(--accent); font-size: 12px; }
.dims { display:grid; grid-template-columns: repeat(5, auto); gap: 2px 12px; margin-top: 6px;
        font-size: 12px; font-variant-numeric: tabular-nums; color: var(--muted); }
.empty { color: var(--muted); padding: 24px 0; }
#cards { position: fixed; top: 16px; right: 16px; width: 260px; max-width: calc(100vw - 32px);
         display: flex; flex-direction: column; gap: 8px; z-index: 10; pointer-events: none; }
.card { background: var(--card); border: 1px solid var(--line); border-left: 4px solid var(--wait);
        border-radius: 6px; padding: 10px 12px; box-shadow: 0 4px 12px rgba(0,0,0,.15);
        transform: translateX(calc(100% + 24px)); transition: transform .35s ease, opacity .35s ease; }
.card.in { transform: none; }
.card.out { opacity: 0; transform: translateX(calc(100% + 24px)); }
.card.AC { border-left-color: var(--ac); } .card.ng { border-left-color: var(--ng); }
.card .who { font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card .who span { color: var(--muted); font-weight: 400; font-size: 12px; margin-left: 6px; }
.card .what { font-size: 13px; margin-top: 2px; font-variant-numeric: tabular-nums; }
@media (prefers-reduced-motion: reduce) { .card, .card.out { transition: none; } tr.flash td { animation: none; } }
"""


def _detail(r):
    dims = "".join("<span>d=%d: %.3f</span>" % (d, t) for d, t in sorted(r["times"].items()))
    return '<details><summary>次元ごと</summary><div class="dims">%s</div></details>' % dims


def _verdict_cell(s):
    if s["status"] != DONE:
        return '<span class="v-wait">%s</span>' % html.escape(s["text"])
    cls = "v-AC" if s["verdict"] == "AC" else "v-ng"
    return '<span class="%s" title="%s">%s</span>' % (cls, html.escape(s["verdict_name"]), s["verdict"])


# 表示する列: (見出し, セルの class, セルの中身)
_RANK = ("順位", "rank", lambda r: str(r["rank"]))
_NAME = ("名前", "", lambda r: html.escape(r["name"]))
_ID = ("提出 ID", "num", lambda r: str(r["id"]))
_SCORE = ("スコア (秒)", "num score", lambda r: "%.3f" % r["score"])
_DETAIL = ("内訳", "", _detail)
_TIME = ("提出時刻", "", lambda r: r["submitted_at"])
_COUNT = ("提出回数", "num", lambda r: str(r["submissions"]))
_VERDICT = ("判定", "", _verdict_cell)
_SUB_SCORE = ("スコア (秒)", "num", lambda s: "%.3f" % s["score"] if s.get("score") is not None else "")
COLUMNS = {
    BEST: [_RANK, _NAME, _SCORE, _DETAIL, _TIME, _COUNT],
    ALL: [_RANK, _NAME, _ID, _SCORE, _DETAIL, _TIME],
    SUBS: [_ID, _TIME, _NAME, _VERDICT, _SUB_SCORE],
}
EMPTY = {BEST: "まだ AC した提出はありません。", ALL: "まだ AC した提出はありません。", SUBS: "まだ提出はありません。"}


def _row_class(view, r):
    if view == SUBS:
        return ""
    return "r%d" % r["rank"] if r["rank"] <= MEDAL_RANKS else ""


def table(view, data):
    """表の HTML。行には data-key (変わったら光らせる) と data-id (内訳の開閉を保つ) を付ける。"""
    if not data:
        return '<p class="empty">%s</p>' % EMPTY[view]
    cols = COLUMNS[view]
    head = "".join('<th class="%s">%s</th>' % (cls, title) for title, cls, _ in cols)
    body = "".join(
        '<tr class="%s" data-id="%d" data-key="%s">%s</tr>' % (
            _row_class(view, r), r["id"],
            html.escape("%s|%s|%s" % (r.get("rank"), r["id"], r.get("text") or r.get("verdict"))),
            "".join('<td class="%s">%s</td>' % (cls, cell(r)) for _, cls, cell in cols))
        for r in data)
    return '<div class="wrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, body)


def board(db, view):
    """ページの差し替え部分 (表の HTML) とカード用の提出一覧。/api/board の中身。"""
    subs = submissions(db)
    return {"html": table(view, subs if view == SUBS else rows(db, view)), "submissions": subs}


SCRIPT = """
(function () {
  var POLL = %(poll)d * 1000, HOLD = %(hold)d * 1000, VIEW = %(view)s;
  var board = document.getElementById("board"), cardsBox = document.getElementById("cards");
  var updated = document.getElementById("updated");
  var cards = {};    // 提出 ID -> {el, done}
  var seen = null;   // 表示済みの最大の提出 ID (最初の取得では判定済みのカードは出さない)

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  function what(s) {
    if (s.status !== "done") return s.text;
    if (s.verdict !== "AC") return s.verdict + " (" + s.verdict_name + ")";
    return "AC  " + s.score.toFixed(3) + " 秒" + (s.rank ? "  " + s.rank + " 位" : "");
  }
  function cls(s) { return s.status !== "done" ? "" : s.verdict === "AC" ? "AC" : "ng"; }

  function showCard(s) {
    var c = cards[s.id];
    if (!c) {
      var el = document.createElement("div");
      el.className = "card";
      cardsBox.appendChild(el);
      c = cards[s.id] = {el: el, done: false};
      requestAnimationFrame(function () { requestAnimationFrame(function () { el.classList.add("in"); }); });
    }
    c.el.className = "card in " + cls(s);
    c.el.innerHTML = '<div class="who">' + esc(s.name) + "<span>#" + s.id + "</span></div>" +
                     '<div class="what">' + esc(what(s)) + "</div>";
    if (s.status === "done" && !c.done) {
      c.done = true;
      setTimeout(function () {
        c.el.classList.add("out");
        setTimeout(function () { c.el.remove(); delete cards[s.id]; }, 400);
      }, HOLD);
    }
  }

  function swapBoard(htmlText) {
    var old = {}, open = {};
    board.querySelectorAll("tr[data-id]").forEach(function (tr) {
      old[tr.dataset.id] = tr.dataset.key;
      if (tr.querySelector("details[open]")) open[tr.dataset.id] = true;
    });
    var first = seen === null;
    board.innerHTML = htmlText;
    board.querySelectorAll("tr[data-id]").forEach(function (tr) {
      if (open[tr.dataset.id]) tr.querySelector("details").open = true;
      if (!first && old[tr.dataset.id] !== tr.dataset.key) tr.classList.add("flash");
    });
  }

  function poll() {
    fetch("/api/board?view=" + VIEW, {cache: "no-store"})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        swapBoard(d.html);
        var subs = d.submissions.slice().reverse();  // 古い順にカードを積む
        subs.forEach(function (s) {
          var isNew = seen === null ? s.status !== "done" : s.id > seen;
          if (cards[s.id] || isNew) showCard(s);
        });
        subs.forEach(function (s) { if (seen === null || s.id > seen) seen = s.id; });
        if (seen === null) seen = 0;
        updated.textContent = new Date().toLocaleTimeString("ja-JP");
      })
      .catch(function () { updated.textContent = "接続できません (再試行中)"; })
      .then(function () { setTimeout(poll, POLL); });
  }
  poll();
})();
"""


def render(cfg, db, view):
    tabs = "".join('<a href="/?view=%s" class="%s">%s</a>' % (v, "on" if v == view else "", label)
                   for v, label in VIEWS.items())
    dims = sorted(c["d"] for c in cfg.problem.cases if c["phase"] == SCORE)
    return """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<noscript><meta http-equiv="refresh" content="30"></noscript>
<title>順位表</title><style>%(css)s</style></head>
<body><main>
<h1>順位表</h1>
<div class="sub">スコア = スコア用ケース (d=%(dmin)d〜%(dmax)d) の実行時間の和。小さいほど上位。自動で更新 (最終更新 <span id="updated">-</span>)</div>
<nav class="tabs">%(tabs)s</nav>
<div id="board">%(table)s</div>
</main>
<div id="cards" aria-live="polite"></div>
<script>%(script)s</script>
</body></html>
""" % {"css": CSS, "dmin": dims[0], "dmax": dims[-1], "tabs": tabs,
       "table": board(db, view)["html"],
       "script": SCRIPT % {"poll": POLL_SEC, "hold": CARD_HOLD_SEC, "view": json.dumps(view)}}
