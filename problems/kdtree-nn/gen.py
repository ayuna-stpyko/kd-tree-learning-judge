"""テストケースの定義と生成。

ケースは名前から決まる乱数シードで生成するので、同じ C なら毎回同じ内容になる。
"""
import random
import zlib

COORD = 10**8

# スコア用ケースの設定 (D -> (分布, Q を N の何倍にするか))。
# Q はジャッジサーバ上で参照解が各ケース 0.3〜0.5 秒程度になるように調整する。
# tools/selftest.py の ac の結果に次元ごとの時間が出るので、それを見て比率を変え、make_tests.py で作り直す。
SCORE_SPEC = {
    1: ("uniform", 0.5),
    2: ("uniform", 0.5),
    3: ("uniform", 0.5),
    4: ("uniform", 0.5),
    5: ("cluster", 0.5),
    6: ("cluster", 0.5),
    7: ("cluster", 0.5),
    8: ("cluster", 0.4),
    9: ("cluster", 0.5),
    10: ("cluster", 0.5),
}


def _clamp(v):
    return -COORD if v < -COORD else COORD if v > COORD else v


def pts_uniform(rng, n, d, lo=-COORD, hi=COORD):
    return [rng.randint(lo, hi) for _ in range(n * d)]


def pts_cluster(rng, n, d, k=64):
    centers = [[rng.randint(-COORD // 2, COORD // 2) for _ in range(d)] for _ in range(k)]
    sigma = COORD // 50
    X = []
    for _ in range(n):
        c = centers[rng.randrange(k)]
        for j in range(d):
            X.append(_clamp(int(rng.gauss(c[j], sigma))))
    return X


def pts_same(rng, n, d):
    p = [rng.randint(-COORD, COORD) for _ in range(d)]
    return p * n


def pts_line(rng, n, d):
    """等間隔に一直線に並んだ点。内側の点には等距離の隣が 2 つあり、番号の小さい方が答え。"""
    while True:
        v = [rng.randint(-3, 3) for _ in range(d)]
        if any(v):
            break
    step = rng.randint(1, 1000)
    base = [rng.randint(-1000, 1000) for _ in range(d)]
    ts = list(range(n))
    rng.shuffle(ts)  # 直線上の位置と番号の対応をばらばらにする
    X = []
    for t in ts:
        for j in range(d):
            X.append(base[j] + t * step * v[j])
    return X


def pts_extreme(rng, n, d):
    choices = [-COORD, COORD, -COORD + 1, COORD - 1, 0]
    X = []
    for _ in range(n):
        for _ in range(d):
            X.append(rng.choice(choices) if rng.random() < 0.8 else rng.randint(-COORD, COORD))
    return X


def pts_dupclusters(rng, n, d):
    """少数の点を大量に複製したもの。自分と同じ座標の別の点が答えになる。"""
    base = [[rng.randint(-50, 50) for _ in range(d)] for _ in range(max(2, n // 40))]
    X = []
    for _ in range(n):
        X.extend(rng.choice(base))
    return X


def pts_sorted(rng, n, d):
    pts = [[rng.randint(-COORD, COORD) for _ in range(d)] for _ in range(n)]
    pts.sort()
    return [v for p in pts for v in p]


def all_queries(rng, n):
    qs = list(range(1, n + 1))
    rng.shuffle(qs)
    return qs


def rand_queries(rng, n, q):
    return [rng.randint(1, n) for _ in range(q)]


def _correctness_cases(C):
    out = []
    for d in range(1, 11):
        mid_n = max(2, min(C // d, 20000) // 4)

        def two(rng, d=d):
            return 2, d, pts_uniform(rng, 2, d), [2, 1]

        def same(rng, d=d):
            n = 10
            return n, d, pts_same(rng, n, d), all_queries(rng, n)

        def tiny(rng, d=d):
            n = min(300, C // d)
            return n, d, pts_uniform(rng, n, d, 0, 2), all_queries(rng, n)

        def line(rng, d=d):
            n = min(500, C // d)
            return n, d, pts_line(rng, n, d), all_queries(rng, n)

        def extreme(rng, d=d):
            n = min(200, C // d)
            return n, d, pts_extreme(rng, n, d), all_queries(rng, n)

        def dupcl(rng, d=d):
            n = min(1000, C // d)
            return n, d, pts_dupclusters(rng, n, d), all_queries(rng, n)

        def mid(rng, d=d, n=mid_n):
            X = pts_sorted(rng, n, d) if d % 2 else pts_cluster(rng, n, d)
            return n, d, X, rand_queries(rng, n, min(n, 2000))

        for kind, fn in (("two", two), ("same", same), ("tiny", tiny), ("line", line),
                         ("extreme", extreme), ("dupcl", dupcl), ("mid", mid)):
            out.append(("correctness", "c%02d_%s" % (d, kind), fn))
    return out


def _score_cases(C):
    out = []
    for d in range(1, 11):
        dist, ratio = SCORE_SPEC[d]
        n = C // d

        def score(rng, d=d, n=n, dist=dist, ratio=ratio):
            X = pts_uniform(rng, n, d) if dist == "uniform" else pts_cluster(rng, n, d)
            q = max(1, min(n, int(n * ratio)))
            return n, d, X, rand_queries(rng, n, q)

        out.append(("score", "d%02d" % d, score))
    return out


def cases(C):
    """[(phase, name, fn)]。fn(rng) -> (n, d, X(平らな座標リスト), queries(1-indexed))"""
    return _correctness_cases(C) + _score_cases(C)


def make(name, fn):
    rng = random.Random(zlib.crc32(name.encode()))
    return fn(rng)


def format_input(n, d, X, queries):
    lines = ["%d %d" % (n, d)]
    for i in range(n):
        lines.append(" ".join(map(str, X[i * d:(i + 1) * d])))
    lines.append(str(len(queries)))
    lines.extend(map(str, queries))
    return "\n".join(lines) + "\n"
