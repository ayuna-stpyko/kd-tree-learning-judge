#!/usr/bin/env python3
"""提出を一覧・表示する (運営者用)。

    tools/show.py              名前と問題ごとの提出数・AC 数・最良スコア
    tools/show.py alice        alice の提出一覧
    tools/show.py alice 31     提出 31 のコードと判定結果
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from judge import config  # noqa: E402
from judge.common import SHORT_DATETIME_FMT, fmt_time, load_result, submission_path  # noqa: E402
from judge.db import DB  # noqa: E402

SUBMISSIONS_DIR = os.path.join(config.ROOT, "submissions")


def fmt_score(score):
    return "%.3f" % score if score is not None else "-"


def show_names(db):
    print("%-20s %-10s %6s %5s %10s  %s" % ("名前", "問題", "提出数", "AC", "最良", "最終提出"))
    for r in db.summary_by_name():
        print("%-20s %-10s %6d %5d %10s  %s" % (r["name"], r["problem"], r["n"], r["ac"] or 0, fmt_score(r["best"]),
                                                fmt_time(r["last"], SHORT_DATETIME_FMT)))


def show_submissions(db, name):
    rows = db.by_name(name)
    if not rows:
        sys.exit("%s の提出はありません" % name)
    print("%6s  %-15s %-10s %-8s %-4s %10s  %s" % ("ID", "時刻", "問題", "状態", "判定", "スコア", "失敗したケース"))
    for r in rows:
        res = load_result(r)
        f = res.get("failed")
        where = "%s #%d (d=%d)" % (f["phase"], f["index"], f["d"]) if f else ""
        if res.get("message"):
            where += " " + res["message"]
        print("%6d  %-15s %-10s %-8s %-4s %10s  %s" % (r["id"], fmt_time(r["created_at"], SHORT_DATETIME_FMT),
                                                      r["problem"], r["status"], r["verdict"] or "-",
                                                      fmt_score(r["score"]), where))


def show_one(name, sid):
    for ext in ("py", "json"):
        path = submission_path(SUBMISSIONS_DIR, name, sid, ext)
        print("=" * 20, path)
        if not os.path.exists(path):
            print("(まだ判定が終わっていません)" if ext == "json" else "(ファイルがありません)")
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            if ext == "py":
                print(f.read())
            else:
                data = json.load(f)
                data.pop("cases", None)
                print(json.dumps(data, ensure_ascii=False, indent=1))


def main():
    path = config.db_path()
    if not os.path.exists(path):
        sys.exit("まだ提出がありません (%s が無い)" % path)
    args = sys.argv[1:]
    if not args:
        show_names(DB(path))
    elif len(args) == 1:
        show_submissions(DB(path), args[0])
    else:
        show_one(args[0], int(args[1]))


if __name__ == "__main__":
    main()
