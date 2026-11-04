#!/usr/bin/env python3
"""動いているジャッジに、判定が分かっている提出を送って結果を確認する。

    python3 tools/selftest.py [--url http://127.0.0.1:8000] [--skip mle,mlec]

名前は "_selftest_..." を使う ("_" で始まる名前は順位表に載らない)。
練習問題 (nn-1d, nn-2d-l1) にも参照解などを送り、問題ごとに判定が分かれることを確かめる。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
from http import HTTPStatus
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = os.path.join(ROOT, "tests", "submissions")
LIB = os.path.join(ROOT, "problems", "lib")
REFERENCE = os.path.join(LIB, "reference.py")
BRUTE = os.path.join(LIB, "brute.py")
METRIC_LINE = 'METRIC = "l2"\n'  # reference.py / brute.py の距離の指定

DEFAULT_URL = "http://127.0.0.1:8000"
HTTP_TIMEOUT_SEC = 30
POLL_SEC = 1

# (項目, 問題, ファイル, 距離 (METRIC の行を書き換える。None ならそのまま), 期待する判定)
EXPECT = [
    ("ac", "kdtree-nn", REFERENCE, None, "AC"),
    ("wa", "kdtree-nn", os.path.join(SUB, "wa.py"), None, "WA"),
    ("tle", "kdtree-nn", os.path.join(SUB, "tle.py"), None, "TLE"),
    ("re", "kdtree-nn", os.path.join(SUB, "re.py"), None, "RE"),
    ("ce", "kdtree-nn", os.path.join(SUB, "ce.py"), None, "CE"),
    ("ole", "kdtree-nn", os.path.join(SUB, "ole.py"), None, "OLE"),
    ("mle", "kdtree-nn", os.path.join(SUB, "mle.py"), None, "MLE"),
    ("mlec", "kdtree-nn", os.path.join(SUB, "mle_compile.py"), None, "MLE"),
    ("cheat", "kdtree-nn", os.path.join(SUB, "cheat.py"), None, "WA"),
    ("ac1d", "nn-1d", REFERENCE, None, "AC"),
    ("tle1d", "nn-1d", BRUTE, None, "TLE"),  # 全探索は大きいケースで TLE
    ("acl1", "nn-2d-l1", REFERENCE, "l1", "AC"),
    ("wal1", "nn-2d-l1", REFERENCE, None, "WA"),  # ユークリッド距離のままでは WA
    ("tlel1", "nn-2d-l1", BRUTE, "l1", "TLE"),
]


def source(path, metric):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if metric is not None:
        assert METRIC_LINE in src, path
        src = src.replace(METRIC_LINE, 'METRIC = "%s"\n' % metric, 1)
    return src


def call(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except urllib.error.URLError as e:
        sys.exit("ジャッジに接続できません (%s): %s" % (url, e.reason))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--skip", default="", help="省略する項目 (カンマ区切り。例: mle,mlec)")
    args = ap.parse_args()
    skip = set(x for x in args.skip.split(",") if x)
    tag = time.strftime("%H%M%S")

    ids = {}
    for key, problem, path, metric, exp in EXPECT:
        if key in skip:
            continue
        code, res = call(args.url + "/api/submit", {"name": "_selftest_%s_%s" % (key, tag), "problem": problem,
                                                    "source": source(path, metric)})
        if code != 200:
            sys.exit("submit %s failed: %s %s" % (key, code, res))
        ids[key] = (res["id"], exp)
        print("submitted %-6s %-9s -> #%d" % (key, problem, res["id"]))

    ok = True
    for key, (sid, exp) in ids.items():
        while True:
            _, st = call("%s/api/submissions/%d" % (args.url, sid))
            if st["status"] == "done":
                break
            time.sleep(POLL_SEC)
        good = st["verdict"] == exp
        ok &= good
        extra = ""
        if st.get("failed"):
            f = st["failed"]
            extra = " (%s #%d d=%d)" % (f["phase"], f["index"], f["d"])
        if st.get("message"):
            extra += " " + st["message"]
        if st.get("score") is not None:
            extra += " score=%.3f" % st["score"]
        print("%s %-6s #%-4d expected %-4s got %-4s%s" % ("OK  " if good else "FAIL", key, sid, exp,
                                                         st["verdict"], extra))
        if st.get("score_times"):
            print("       次元ごとの時間: " + "  ".join("d=%s %.3f" % (d, t) for d, t in
                                                  sorted(st["score_times"].items(), key=lambda x: int(x[0]))))
    # 連続提出の制限
    first = next(e[0] for e in EXPECT if e[0] not in skip)
    code, res = call(args.url + "/api/submit", {"name": "_selftest_%s_%s" % (first, tag), "source": "print(1)\n"})
    good = code == HTTPStatus.TOO_MANY_REQUESTS
    ok &= good
    print("%s rate limit -> %s %s" % ("OK  " if good else "FAIL", code, res.get("error")))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
