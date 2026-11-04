"""全探索解 O(QND)。正解の検算と、大きいケースで TLE になることの確認に使う。

metric: "l2" (ユークリッド距離。比べるのは二乗距離) か "l1" (マンハッタン距離)。
提出として実行したときは METRIC を使う。
"""
import sys

METRIC = "l2"


def nearest_brute(X, d, n, qi, metric=METRIC):
    l1 = metric == "l1"
    base = qi * d
    q = X[base:base + d]
    bd = -1
    bi = -1
    for p in range(n):
        if p == qi:
            continue
        o = p * d
        s = 0
        for j in range(d):
            t = X[o + j] - q[j]
            s += (t if t >= 0 else -t) if l1 else t * t
        if bd < 0 or s < bd:  # 番号の小さい順に見るので、同じ距離なら先に見つけた方が残る
            bd, bi = s, p
    return bi


def main():
    data = sys.stdin.buffer.read().split()
    n, d = int(data[0]), int(data[1])
    X = list(map(int, data[2:2 + n * d]))
    pos = 2 + n * d
    q = int(data[pos])
    out = [nearest_brute(X, d, n, int(s) - 1) + 1 for s in data[pos + 1:pos + 1 + q]]
    sys.stdout.write("\n".join(map(str, out)) + "\n")


if __name__ == "__main__":
    main()
