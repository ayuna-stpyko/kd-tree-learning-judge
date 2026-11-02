#!/usr/bin/env python3
"""提出を判定し直す (待機中に戻す)。ジャッジが動いていれば順に判定される。

    tools/rejudge.py 31 32 33
    tools/rejudge.py --all-ac     AC の提出をすべて (テストケースを変えたときなど)
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "judge.db")


def main():
    c = sqlite3.connect(DB, timeout=30)
    if sys.argv[1:] == ["--all-ac"]:
        ids = [r[0] for r in c.execute("SELECT id FROM submissions WHERE verdict='AC' ORDER BY id")]
    else:
        ids = [int(x) for x in sys.argv[1:]]
    if not ids:
        sys.exit(__doc__)
    with c:
        for sid in ids:
            c.execute("UPDATE submissions SET status='queued', verdict=NULL, score=NULL, result=NULL, "
                      "progress=NULL, finished_at=NULL WHERE id=? AND status='done'", (sid,))
    print("待機中に戻しました:", " ".join(map(str, ids)))


if __name__ == "__main__":
    main()
