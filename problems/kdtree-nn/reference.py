"""参照解 (kd-tree)。提出と同じ形式で標準入出力を使う。

make_tests.py からは build / nearest を import して正解の生成にも使う。
"""
import sys

LEAF = 8


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
        step = max(1, (hi - lo) // 64)
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


def nearest(X, d, perm, axis, n, qi):
    """点 qi 以外で最も近い点の番号 (0-indexed)。同じ距離なら番号が最小のもの。"""
    base = qi * d
    q = X[base:base + d]
    bd = 1 << 62
    bi = -1
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
