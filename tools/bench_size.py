#!/usr/bin/env python3
"""入力の大きさ (C = N*D) を決めるための計測スクリプト。

PyPy / CPython どちらでも動く (標準ライブラリのみ)。ジャッジサーバでは PyPy で実行する:
    docker run --rm -v "$PWD:/w" -w /w --cpuset-cpus 2 kdjudge-sandbox pypy3 tools/bench_size.py

    tools/bench_size.py [読み込みを測る C (カンマ区切り)] [サンプルするクエリ数] [kd-tree を測る C]

計測するもの:
  1. 入力の読み込み時間 (C を変えて)
  2. 参照解 (kd-tree) の構築時間と、1 クエリあたりの時間・調べた点の数 (D と分布ごと)
  3. 全探索の 1 クエリあたりの時間 (Q の下限を決めるため)
"""
import io
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "problems", "lib"))

import brute  # noqa: E402
import gen  # noqa: E402
import reference  # noqa: E402

DEFAULT_READ_CS = "250000,500000,1000000,2000000"
DEFAULT_SAMPLE_QUERIES = 2000
TARGET_REF_SEC = 0.4  # 参照解の 1 ケースの目標時間
TIME_LIMIT_SEC = 2.0
READ_REPEAT = 3
WARMUP_FRACTION = 10  # サンプルの 1/10 を JIT のウォームアップに使う
BRUTE_SAMPLE_QUERIES = 3
MAX_D = 10
DISTRIBUTIONS = {
    "uniform": gen.pts_uniform,
    "cluster": gen.pts_cluster,
    "lowdim": gen.pts_lowdim,
}


def bench_read(C):
    rng = random.Random(1)
    data = " ".join(str(rng.randint(-gen.COORD, gen.COORD)) for _ in range(C)).encode()
    best = float("inf")
    for _ in range(READ_REPEAT):
        t = time.perf_counter()
        list(map(int, io.BytesIO(data).read().split()))
        best = min(best, time.perf_counter() - t)
    return best, len(data)


def bench_kdtree(C, nq, rng):
    print("D\tdist\tN\tbuild(s)\tus/query\tvisited/query\tQ(%.1fs分)\tQ_brute_TLE(%.0fs)"
          % (TARGET_REF_SEC, TIME_LIMIT_SEC))
    for d in range(1, MAX_D + 1):
        n = C // d
        for dist, make in DISTRIBUTIONS.items():
            X = make(rng, n, d)
            t = time.perf_counter()
            perm, axis = reference.build(X, n, d)
            tb = time.perf_counter() - t
            qs = [rng.randrange(n) for _ in range(nq)]
            for qi in qs[:nq // WARMUP_FRACTION]:
                reference.nearest(X, d, perm, axis, n, qi)
            stats = reference.Stats()
            t = time.perf_counter()
            for qi in qs:
                reference.nearest(X, d, perm, axis, n, qi, stats)
            tq = (time.perf_counter() - t) / nq
            t = time.perf_counter()
            for qi in qs[:BRUTE_SAMPLE_QUERIES]:
                brute.nearest_brute(X, d, n, qi)
            tbr = (time.perf_counter() - t) / BRUTE_SAMPLE_QUERIES
            print("%d\t%s\t%d\t%.2f\t%.1f\t%.0f\t%d\t%d" % (
                d, dist, n, tb, tq * 1e6, stats.visited / nq, int(TARGET_REF_SEC / tq),
                int(TIME_LIMIT_SEC / tbr) + 1))
            sys.stdout.flush()


def main():
    print("# implementation:", sys.implementation.name, sys.version.split()[0])
    read_cs = [int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_READ_CS).split(",")]
    nq = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SAMPLE_QUERIES
    C = int(sys.argv[3]) if len(sys.argv) > 3 else max(read_cs)

    print("\n## 1. 入力の読み込み (bytes.split + int)")
    print("C\tbytes(MB)\tread(s)")
    for c in read_cs:
        t, nb = bench_read(c)
        print("%d\t%.1f\t%.3f" % (c, nb / 1e6, t))

    print("\n## 2. kd-tree (C = N*D = %d, クエリ %d 個をサンプルして外挿)" % (C, nq))
    bench_kdtree(C, nq, random.Random(42))


if __name__ == "__main__":
    main()
