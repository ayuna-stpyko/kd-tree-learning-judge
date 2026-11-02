"""全探索解 O(QND)。正解の検算と、スコア用ケースで TLE になることの確認に使う。"""
import sys


def nearest_brute(X, d, n, qi):
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
            s += t * t
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
