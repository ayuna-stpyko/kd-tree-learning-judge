"""参照解 (kd-tree)。提出と同じ形式で標準入出力を使う。

make_tests.py からは build / nearest を import して正解の生成にも使う。
"""
import sys

LEAF = 8  # この個数以下の区間は分割せず、まとめて調べる
AXIS_SAMPLES = 64  # 分割軸を選ぶとき、広がりを見るのに使う点の数


class Stats:
    """計測用 (tools/bench_size.py): 距離を計算した点の数。"""
    visited = 0


def build(X, n, d):
    """点の番号の並び perm と、各ノード (区間の中央) の分割軸 axis を返す。

    区間 [lo, hi) の中央 mid = (lo + hi) // 2 がノード。左の子が [lo, mid)、右の子が [mid + 1, hi)。
    """
    perm = list(range(n))
    axis = [0] * n
    stack = [(0, n)]
    while stack:
        lo, hi = stack.pop()
        if hi - lo <= LEAF:
            continue
        step = max(1, (hi - lo) // AXIS_SAMPLES)
        best_a, best_w = 0, -1
        for a in range(d):
            vals = [X[perm[i] * d + a] for i in range(lo, hi, step)]
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


def nearest(X, d, perm, axis, n, qi, stats=None):
    """点 qi 以外で最も近い点の番号 (0-indexed)。同じ距離なら番号が最小のもの。"""
    base = qi * d
    q = X[base:base + d]
    bd = 1 << 62  # 二乗距離の最大値 (10 * (2 * 10**8)**2 = 4 * 10**17) より大きい
    bi = -1
    visited = 0
    stack = [(0, n, 0)]
    while stack:
        lo, hi, lb = stack.pop()
        if lb > bd:
            continue
        while True:
            # 距離の計算は葉とノードの 2 か所に書いている。関数にすると CPython で正解を作るとき
            # (make_tests.py) に呼び出しの分だけ遅くなるため、ここだけは意図的に展開している。
            if hi - lo <= LEAF:
                visited += hi - lo
                for i in range(lo, hi):
                    p = perm[i]
                    if p == qi:
                        continue
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
            visited += 1
            if p != qi:
                s = 0
                for j in range(d):
                    t = X[o + j] - q[j]
                    s += t * t
                if s < bd or (s == bd and p < bi):
                    bd, bi = s, p
            a = axis[mid]
            diff = q[a] - X[o + a]
            # 同じ座標の点は分割面の左右どちらにも入りうるので、diff == 0 でも反対側を残す
            if diff < 0:
                stack.append((mid + 1, hi, diff * diff))
                hi = mid
            else:
                stack.append((lo, mid, diff * diff))
                lo = mid + 1
            if lb > bd:
                break
    if stats is not None:
        stats.visited += visited
    return bi


def main():
    data = sys.stdin.buffer.read().split()
    n, d = int(data[0]), int(data[1])
    X = list(map(int, data[2:2 + n * d]))
    pos = 2 + n * d
    q = int(data[pos])
    queries = data[pos + 1:pos + 1 + q]
    perm, axis = build(X, n, d)
    out = []
    for s in queries:
        out.append(nearest(X, d, perm, axis, n, int(s) - 1) + 1)
    sys.stdout.write("\n".join(map(str, out)) + "\n")


if __name__ == "__main__":
    main()
