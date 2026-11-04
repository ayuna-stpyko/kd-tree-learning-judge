"""問題のテストケース (tests/) を生成する。

    python3 problems/lib/make_tests.py problems/kdtree-nn            # problem.json の max_nd で生成
    python3 problems/lib/make_tests.py problems/kdtree-nn --nd 20000 # 開発用に小さく生成

- problem.json の dims (次元)、metric (距離)、ranked (順位表に載るか) でケースの種類が決まる (gen.py)。
- 正解は参照解 (kd-tree) で作り、全探索解で検算する
  (小さいケースは全クエリ、大きいケースはランダムに選んだ一部のクエリ)。
- validator で制約を確認する。
- 出力: <問題>/tests/correctness/*.in|.out, <問題>/tests/score/dNN.in|.out, <問題>/tests/manifest.json
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

# N * Q がこれ以下なら全クエリを全探索で検算する
CHECK_ALL_MAX_NQ = 2 * 10**7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("problem", help="問題のディレクトリ (problem.json がある所)")
    ap.add_argument("--nd", type=int, default=None, help="N*D の上限 (既定: problem.json の max_nd)")
    ap.add_argument("--out", default=None, help="出力先 (既定: <問題>/tests)")
    ap.add_argument("--check", type=int, default=200, help="大きいケースで全探索と照合するクエリ数")
    args = ap.parse_args()
    with open(os.path.join(args.problem, "problem.json")) as f:
        problem = json.load(f)
    nd = args.nd or problem["max_nd"]
    out_dir = args.out or os.path.join(args.problem, "tests")
    dims, metric, ranked = problem["dims"], problem["metric"], problem["ranked"]

    manifest = {"max_nd": nd, "cases": []}
    for phase in ("correctness", "score"):
        os.makedirs(os.path.join(out_dir, phase), exist_ok=True)

    for phase, name, fn in gen.cases(nd, dims, ranked):
        t0 = time.time()
        n, d, X, queries = gen.make(name, fn)
        text = gen.format_input(n, d, X, queries)
        stats = validator.validate(text.encode(), nd, dims)

        perm, axis = reference.build(X, n, d)
        ans = [reference.nearest(X, d, perm, axis, n, qi - 1, metric=metric) + 1 for qi in queries]

        if n * len(queries) <= CHECK_ALL_MAX_NQ:
            check = range(len(queries))
        else:
            rng = random.Random(1)
            check = [rng.randrange(len(queries)) for _ in range(min(args.check, len(queries)))]
        for k in check:
            b = brute.nearest_brute(X, d, n, queries[k] - 1, metric) + 1
            if b != ans[k]:
                sys.exit("%s: 参照解と全探索解が一致しない (query #%d: %d vs %d)" % (name, k + 1, ans[k], b))

        base = os.path.join(out_dir, phase, name)
        with open(base + ".in", "w") as f:
            f.write(text)
        with open(base + ".out", "w") as f:
            f.write("\n".join(map(str, ans)) + "\n")
        manifest["cases"].append({"phase": phase, "name": name, "d": d, "n": n, "q": len(queries)})
        print("%-12s %-14s N=%-7d D=%-2d Q=%-7d dup=%-6d %.1fs" % (
            phase, name, n, d, len(queries), stats["duplicates"], time.time() - t0))
        sys.stdout.flush()

    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("done:", len(manifest["cases"]), "cases ->", out_dir)


if __name__ == "__main__":
    main()
