#!/usr/bin/env python3
"""提出を判定し直す (待機中に戻す)。ジャッジが動いていれば順に判定される。

    tools/rejudge.py 31 32 33
    tools/rejudge.py --all-ac     AC の提出をすべて (テストケースを変えたときなど)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from judge import config  # noqa: E402
from judge.db import DB  # noqa: E402


def main():
    db = DB(config.db_path())
    args = sys.argv[1:]
    ids = db.accepted_ids() if args == ["--all-ac"] else [int(x) for x in args]
    if not ids:
        sys.exit(__doc__)
    db.requeue(ids)
    print("待機中に戻しました:", " ".join(map(str, ids)))


if __name__ == "__main__":
    main()
