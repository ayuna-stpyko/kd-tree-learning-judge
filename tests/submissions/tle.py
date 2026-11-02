# 期待: TLE (全探索。正誤判定用は通り、スコア用で時間切れになる)
import sys
data = sys.stdin.buffer.read().split()
n, d = int(data[0]), int(data[1])
X = list(map(int, data[2:2 + n * d]))
pos = 2 + n * d
q = int(data[pos])
out = []
for s in data[pos + 1:pos + 1 + q]:
    qi = int(s) - 1
    best, bi = -1, -1
    for p in range(n):
        if p == qi:
            continue
        t = 0
        for j in range(d):
            u = X[p * d + j] - X[qi * d + j]
            t += u * u
        if best < 0 or t < best:
            best, bi = t, p
    out.append(bi + 1)
print("\n".join(map(str, out)))
