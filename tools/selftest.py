#!/usr/bin/env python3
"""動いているジャッジに、判定が分かっている提出を送って結果を確認する。

    python3 tools/selftest.py [--url http://127.0.0.1:8000] [--skip mle,mlec]

名前は "_selftest_..." を使う ("_" で始まる名前は順位表に載らない)。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = os.path.join(ROOT, "tests", "submissions")

EXPECT = [
    ("ac", os.path.join(ROOT, "problems", "kdtree-nn", "reference.py"), "AC"),
    ("wa", os.path.join(SUB, "wa.py"), "WA"),
    ("tle", os.path.join(SUB, "tle.py"), "TLE"),
    ("re", os.path.join(SUB, "re.py"), "RE"),
    ("ce", os.path.join(SUB, "ce.py"), "CE"),
    ("ole", os.path.join(SUB, "ole.py"), "OLE"),
    ("mle", os.path.join(SUB, "mle.py"), "MLE"),
    ("mlec", os.path.join(SUB, "mle_compile.py"), "MLE"),
    ("cheat", os.path.join(SUB, "cheat.py"), "WA"),
]


def call(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--skip", default="", help="省略する項目 (カンマ区切り。例: mle,mlec)")
    args = ap.parse_args()
    skip = set(x for x in args.skip.split(",") if x)
    tag = time.strftime("%H%M%S")

    ids = {}
    for key, path, exp in EXPECT:
        if key in skip:
            continue
        with open(path, encoding="utf-8") as f:
            src = f.read()
        code, res = call(args.url + "/api/submit", {"name": "_selftest_%s_%s" % (key, tag), "source": src})
        if code != 200:
            sys.exit("submit %s failed: %s %s" % (key, code, res))
        ids[key] = (res["id"], exp)
        print("submitted %-6s -> #%d" % (key, res["id"]))

    ok = True
    for key, (sid, exp) in ids.items():
        while True:
            _, st = call("%s/api/submissions/%d" % (args.url, sid))
            if st["status"] == "done":
                break
            time.sleep(1)
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
    first = next(k for k, _, _ in EXPECT if k not in skip)
    code, res = call(args.url + "/api/submit", {"name": "_selftest_%s_%s" % (first, tag), "source": "print(1)\n"})
    good = code == 429
    ok &= good
    print("%s rate limit -> %s %s" % ("OK  " if good else "FAIL", code, res.get("error")))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
