#!/usr/bin/env python3
"""入力の大きさ (C = N*D) を決めるための計測スクリプト。

PyPy / CPython どちらでも動く (標準ライブラリのみ)。ジャッジサーバでは
    docker run --rm -v "$PWD/tools:/w" --cpuset-cpus 2 pypy:3-slim pypy3 /w/bench_size.py
のように PyPy で実行して値を確定する。

計測するもの:
  1. 入力の読み込み時間 (C を変えて)
  2. 参照 kd-tree の構築時間と、1 クエリあたりの時間・調べた点の数 (D と分布ごと)
  3. 全探索の 1 距離計算あたりの時間 (Q の下限を決めるため)
"""
import random
import sys
import time

LEAF = 8
COORD = 10**8


# ---------------------------------------------------------------- 生成
def gen_points(n, d, dist, rng):
    if dist == "uniform":
        return [rng.randint(-COORD, COORD) for _ in range(n * d)]
    if dist == "cluster":
        k = 64
        centers = [[rng.randint(-COORD // 2, COORD // 2) for _ in range(d)] for _ in range(k)]
        sigma = COORD // 50
        out = []
        for _ in range(n):
            c = centers[rng.randrange(k)]
            for j in range(d):
                v = int(rng.gauss(c[j], sigma))
                out.append(max(-COORD, min(COORD, v)))
        return out
    if dist == "lowdim":
        # 2 次元の平面上の点を D 次元に埋め込み、小さいノイズを足す
        basis = [[rng.uniform(-1, 1) for _ in range(d)] for _ in range(2)]
        out = []
        s = COORD // 3
        for _ in range(n):
            a, b = rng.uniform(-1, 1), rng.uniform(-1, 1)
            for j in range(d):
                v = int(s * (a * basis[0][j] + b * basis[1][j]) + rng.gauss(0, COORD / 1000))
                out.append(max(-COORD, min(COORD, v)))
        return out
    raise ValueError(dist)


# ---------------------------------------------------------------- kd-tree
def build(X, n, d):
    perm = list(range(n))
    axis = [0] * n
    stack = [(0, n)]
    while stack:
        lo, hi = stack.pop()
        if hi - lo <= LEAF:
            continue
        # 広がりが最大の軸で分割
        best_a, best_w = 0, -1
        for a in range(d):
            vals = [X[perm[i] * d + a] for i in range(lo, hi, max(1, (hi - lo) // 64))]
            w = max(vals) - min(vals)
            if w > best_w:
                best_a, best_w = a, w
        sub = perm[lo:hi]
        sub.sort(key=lambda p: X[p * d + best_a])
        perm[lo:hi] = sub
        mid = (lo + hi) >> 1
        axis[mid] = best_a
        stack.append((lo, mid))
        stack.append((mid + 1, hi))
    return perm, axis


def query(X, d, perm, axis, n, qi):
    base = qi * d
    q = X[base:base + d]
    bd = 1 << 62
    bi = -1
    visited = 0
    stack = [(0, n, 0)]
    while stack:
        lo, hi, lb = stack.pop()
        if lb > bd:
            continue
        while True:
            if hi - lo <= LEAF:
                for i in range(lo, hi):
                    p = perm[i]
                    if p == qi:
                        continue
                    visited += 1
                    o = p * d
                    s = 0
                    for j in range(d):
                        t = X[o + j] - q[j]
                        s += t * t
                    if s < bd or (s == bd and p < bi):
                        bd, bi = s, p
                break
            mid = (lo + hi) >> 1
            p = perm[mid]
            o = p * d
            if p != qi:
                visited += 1
                s = 0
                for j in range(d):
                    t = X[o + j] - q[j]
                    s += t * t
                if s < bd or (s == bd and p < bi):
                    bd, bi = s, p
            a = axis[mid]
            diff = q[a] - X[o + a]
            # 同じ座標の点は左右どちらにも入りうるので、diff == 0 なら両側を探す
            if diff < 0:
                stack.append((mid + 1, hi, diff * diff))
                hi = mid
            else:
                stack.append((lo, mid, diff * diff))
                lo = mid + 1
            if lb > bd:
                break
    return bi, visited


def brute(X, n, d, qi):
    base = qi * d
    q = X[base:base + d]
    bd = 1 << 62
    bi = -1
    for p in range(n):
        if p == qi:
            continue
        o = p * d
        s = 0
        for j in range(d):
            t = X[o + j] - q[j]
            s += t * t
        if s < bd:
            bd, bi = s, p
    return bi


# ---------------------------------------------------------------- 計測
def bench_read(C):
    import io
    rng = random.Random(1)
    data = " ".join(str(rng.randint(-COORD, COORD)) for _ in range(C)).encode()
    best = 1e9
    for _ in range(3):
        t = time.perf_counter()
        xs = list(map(int, io.BytesIO(data).read().split()))
        best = min(best, time.perf_counter() - t)
    assert len(xs) == C
    return best, len(data)


def main():
    impl = sys.implementation.name
    print("# implementation:", impl, sys.version.split()[0])
    Cs = [int(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else ["250000", "500000", "1000000", "2000000"])]
    nq = int(sys.argv[2]) if len(sys.argv) > 2 else 2000

    print("\n## 1. 入力の読み込み (bytes.split + int)")
    print("C\tbytes(MB)\tread(s)")
    for C in Cs:
        t, nb = bench_read(C)
        print(f"{C}\t{nb/1e6:.1f}\t{t:.3f}")

    C = max(Cs) if len(sys.argv) <= 3 else int(sys.argv[3])
    print(f"\n## 2. kd-tree (C = N*D = {C}, クエリ {nq} 個をサンプルして外挿)")
    print("D\tdist\tN\tbuild(s)\tus/query\tvisited/query\tQ(0.4s分)\tQ_brute_TLE(2s)")
    rng = random.Random(42)
    # 全探索の 1 距離計算 (D 要素) あたりの時間を D ごとに測る
    for d in range(1, 11):
        n = C // d
        for dist in ("uniform", "cluster", "lowdim"):
            X = gen_points(n, d, dist, rng)
            t = time.perf_counter()
            perm, axis = build(X, n, d)
            tb = time.perf_counter() - t
            qs = [rng.randrange(n) for _ in range(nq)]
            # JIT のウォームアップ
            for qi in qs[: nq // 10]:
                query(X, d, perm, axis, n, qi)
            t = time.perf_counter()
            vis = 0
            for qi in qs:
                _, v = query(X, d, perm, axis, n, qi)
                vis += v
            tq = (time.perf_counter() - t) / nq
            # 全探索: 数クエリだけ測って 1 クエリの時間を出す
            t = time.perf_counter()
            for qi in qs[:3]:
                brute(X, n, d, qi)
            tbr = (time.perf_counter() - t) / 3
            q_budget = int(0.4 / tq) if tq > 0 else 0
            q_brute = int(2.0 / tbr) + 1
            print(f"{d}\t{dist}\t{n}\t{tb:.2f}\t{tq*1e6:.1f}\t{vis/nq:.0f}\t{q_budget}\t{q_brute}")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
