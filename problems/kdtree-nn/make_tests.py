"""テストケース (tests/) を生成する。

    python3 problems/kdtree-nn/make_tests.py            # problem.json の max_nd で生成
    python3 problems/kdtree-nn/make_tests.py --nd 20000 # 開発用に小さく生成

- 正解は参照解 (kd-tree) で作り、全探索解で検算する
  (正誤判定用は全クエリ、スコア用はランダムに選んだ一部のクエリ)。
- validator で制約を確認する。
- 出力: tests/correctness/*.in|.out, tests/score/dNN.in|.out, tests/manifest.json
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import brute  # noqa: E402
import gen  # noqa: E402
import reference  # noqa: E402
import validator  # noqa: E402


def main():
    with open(os.path.join(HERE, "problem.json")) as f:
        problem = json.load(f)
    ap = argparse.ArgumentParser()
    ap.add_argument("--nd", type=int, default=problem["max_nd"], help="N*D の上限 (既定: problem.json の max_nd)")
    ap.add_argument("--out", default=os.path.join(HERE, "tests"))
    ap.add_argument("--check-score", type=int, default=200, help="スコア用ケースで全探索と照合するクエリ数")
    args = ap.parse_args()

    manifest = {"max_nd": args.nd, "cases": []}
    for phase in ("correctness", "score"):
        os.makedirs(os.path.join(args.out, phase), exist_ok=True)

    for phase, name, fn in gen.cases(args.nd):
        t0 = time.time()
        n, d, X, queries = gen.make(name, fn)
        text = gen.format_input(n, d, X, queries)
        stats = validator.validate(text.encode(), args.nd)

        perm, axis = reference.build(X, n, d)
        ans = [reference.nearest(X, d, perm, axis, n, qi - 1) + 1 for qi in queries]

        if phase == "correctness":
            check = range(len(queries))
        else:
            rng = random.Random(1)
            check = [rng.randrange(len(queries)) for _ in range(min(args.check_score, len(queries)))]
        for k in check:
            b = brute.nearest_brute(X, d, n, queries[k] - 1) + 1
            if b != ans[k]:
                sys.exit("%s: 参照解と全探索解が一致しない (query #%d: %d vs %d)" % (name, k + 1, ans[k], b))

        base = os.path.join(args.out, phase, name)
        with open(base + ".in", "w") as f:
            f.write(text)
        with open(base + ".out", "w") as f:
            f.write("\n".join(map(str, ans)) + "\n")
        manifest["cases"].append({"phase": phase, "name": name, "d": d, "n": n, "q": len(queries)})
        print("%-12s %-14s N=%-7d D=%-2d Q=%-7d dup=%-6d %.1fs" % (
            phase, name, n, d, len(queries), stats["duplicates"], time.time() - t0))
        sys.stdout.flush()

    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("done:", len(manifest["cases"]), "cases ->", args.out)


if __name__ == "__main__":
    main()
