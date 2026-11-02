#!/usr/bin/env python3
"""提出を一覧・表示する (運営者用)。

    tools/show.py              名前ごとの提出数・最良スコア
    tools/show.py alice        alice の提出一覧
    tools/show.py alice 31     提出 31 のコードと判定結果
"""
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "judge.db")
SUBS = os.path.join(ROOT, "submissions")


def fmt_time(t):
    return time.strftime("%m/%d %H:%M:%S", time.localtime(t))


def main():
    if not os.path.exists(DB):
        sys.exit("まだ提出がありません (%s が無い)" % DB)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    args = sys.argv[1:]
    if not args:
        rows = c.execute("SELECT name, COUNT(*) AS n, MIN(CASE WHEN verdict='AC' THEN score END) AS best, "
                         "MAX(created_at) AS last FROM submissions GROUP BY name ORDER BY name").fetchall()
        print("%-20s %6s %10s  %s" % ("名前", "提出数", "最良", "最終提出"))
        for r in rows:
            best = "%.3f" % r["best"] if r["best"] is not None else "-"
            print("%-20s %6d %10s  %s" % (r["name"], r["n"], best, fmt_time(r["last"])))
    elif len(args) == 1:
        rows = c.execute("SELECT * FROM submissions WHERE name=? ORDER BY id", (args[0],)).fetchall()
        if not rows:
            sys.exit("%s の提出はありません" % args[0])
        print("%6s  %-15s %-8s %-4s %10s  %s" % ("ID", "時刻", "状態", "判定", "スコア", "失敗したケース"))
        for r in rows:
            res = json.loads(r["result"]) if r["result"] else {}
            f = res.get("failed")
            where = "%s #%d (d=%d)" % (f["phase"], f["index"], f["d"]) if f else ""
            if res.get("message"):
                where += " " + res["message"]
            score = "%.3f" % r["score"] if r["score"] is not None else "-"
            print("%6d  %-15s %-8s %-4s %10s  %s" % (r["id"], fmt_time(r["created_at"]), r["status"],
                                                    r["verdict"] or "-", score, where))
    else:
        name, sid = args[0], int(args[1])
        py = os.path.join(SUBS, name, "%05d.py" % sid)
        js = os.path.join(SUBS, name, "%05d.json" % sid)
        print("=" * 20, py)
        with open(py, encoding="utf-8", errors="replace") as f:
            print(f.read())
        print("=" * 20, js)
        if os.path.exists(js):
            with open(js, encoding="utf-8") as f:
                d = json.load(f)
            d.pop("cases", None)
            print(json.dumps(d, ensure_ascii=False, indent=1))
        else:
            print("(まだ判定が終わっていません)")


if __name__ == "__main__":
    main()
