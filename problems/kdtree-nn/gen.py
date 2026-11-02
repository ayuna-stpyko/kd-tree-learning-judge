"""テストケースの定義と生成。

ケースは名前から決まる乱数シードで生成するので、同じ C (N*D の上限) なら毎回同じ内容になる。
点の生成関数はすべて (rng, n, d) -> 平らな座標リスト (長さ n*d)。
"""
import random
import zlib

COORD = 10**8  # 座標の絶対値の上限 (問題の制約)
MAX_D = 10

# ---- 点の分布のパラメータ
CLUSTER_COUNT = 64
CLUSTER_CENTER_RANGE = COORD // 2  # 中心は ±この範囲 (クラスタが座標の上限からはみ出しにくいように)
CLUSTER_SIGMA = COORD // 50
LOWDIM_RANK = 2  # 低次元の構造: この次元の平面を D 次元に埋め込む
LOWDIM_SCALE = COORD // 3
LOWDIM_NOISE = COORD / 1000
LINE_DIR_MAX = 3  # 直線の向きの各成分は ±この範囲の整数
LINE_STEP_MAX = 1000
LINE_BASE_RANGE = 1000
TINY_RANGE = (0, 2)  # 座標の範囲が狭い = 重複点・等距離の点が多い
EXTREME_VALUES = (-COORD, COORD, -COORD + 1, COORD - 1, 0)
EXTREME_RATIO = 0.8  # 座標のうち EXTREME_VALUES から選ぶ割合
DUP_RANGE = 50
DUP_COPIES = 40  # 1 つの座標を平均何個複製するか

# ---- スコア用ケース: D -> (分布, Q を N の何倍にするか)
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
    return max(-COORD, min(COORD, v))


def pts_uniform(rng, n, d, lo=-COORD, hi=COORD):
    return [rng.randint(lo, hi) for _ in range(n * d)]


def pts_tiny(rng, n, d):
    return pts_uniform(rng, n, d, *TINY_RANGE)


def pts_cluster(rng, n, d):
    centers = [[rng.randint(-CLUSTER_CENTER_RANGE, CLUSTER_CENTER_RANGE) for _ in range(d)]
               for _ in range(CLUSTER_COUNT)]
    X = []
    for _ in range(n):
        c = rng.choice(centers)
        X.extend(_clamp(int(rng.gauss(c[j], CLUSTER_SIGMA))) for j in range(d))
    return X


def pts_lowdim(rng, n, d):
    """LOWDIM_RANK 次元の平面上の点を D 次元に埋め込み、小さいノイズを足したもの。"""
    basis = [[rng.uniform(-1, 1) for _ in range(d)] for _ in range(LOWDIM_RANK)]
    X = []
    for _ in range(n):
        coef = [rng.uniform(-1, 1) for _ in range(LOWDIM_RANK)]
        for j in range(d):
            v = LOWDIM_SCALE * sum(a * b[j] for a, b in zip(coef, basis)) + rng.gauss(0, LOWDIM_NOISE)
            X.append(_clamp(int(v)))
    return X


def pts_same(rng, n, d):
    return [rng.randint(-COORD, COORD) for _ in range(d)] * n


def pts_line(rng, n, d):
    """等間隔に一直線に並んだ点。内側の点には等距離の隣が 2 つあり、番号の小さい方が答え。"""
    v = [0] * d
    while not any(v):
        v = [rng.randint(-LINE_DIR_MAX, LINE_DIR_MAX) for _ in range(d)]
    step = rng.randint(1, LINE_STEP_MAX)
    base = [rng.randint(-LINE_BASE_RANGE, LINE_BASE_RANGE) for _ in range(d)]
    ts = list(range(n))
    rng.shuffle(ts)  # 直線上の位置と番号の対応をばらばらにする
    return [base[j] + t * step * v[j] for t in ts for j in range(d)]


def pts_extreme(rng, n, d):
    return [rng.choice(EXTREME_VALUES) if rng.random() < EXTREME_RATIO else rng.randint(-COORD, COORD)
            for _ in range(n * d)]


def pts_dupclusters(rng, n, d):
    """少数の点を大量に複製したもの。自分と同じ座標の別の点が答えになる。"""
    base = [[rng.randint(-DUP_RANGE, DUP_RANGE) for _ in range(d)] for _ in range(max(2, n // DUP_COPIES))]
    return [v for _ in range(n) for v in rng.choice(base)]


def pts_sorted(rng, n, d):
    """先頭の座標でソート済みの点 (分割の選び方が悪い実装が遅くなる)。"""
    pts = sorted([rng.randint(-COORD, COORD) for _ in range(d)] for _ in range(n))
    return [v for p in pts for v in p]


def pts_mid(rng, n, d):
    return pts_sorted(rng, n, d) if d % 2 else pts_cluster(rng, n, d)


def all_queries(rng, n):
    qs = list(range(1, n + 1))
    rng.shuffle(qs)
    return qs


def rand_queries(rng, n, q):
    return [rng.randint(1, n) for _ in range(q)]


# ---- 正誤判定用ケース: (種類, N の上限, 点の生成, Q の上限 (None なら全点を 1 回ずつ))
# 各 D について 1 つずつ作る。N は min(N の上限, C // D)。
CORRECTNESS_SPEC = [
    ("two", 2, pts_uniform, None),
    ("same", 10, pts_same, None),
    ("tiny", 300, pts_tiny, None),
    ("line", 500, pts_line, None),
    ("extreme", 200, pts_extreme, None),
    ("dupcl", 1000, pts_dupclusters, None),
    ("mid", 5000, pts_mid, 2000),
]

DISTRIBUTIONS = {"uniform": pts_uniform, "cluster": pts_cluster, "lowdim": pts_lowdim}


def _case(d, n, points, q):
    def make_case(rng):
        X = points(rng, n, d)
        return n, d, X, all_queries(rng, n) if q is None else rand_queries(rng, n, q)
    return make_case


def cases(C):
    """[(phase, name, fn)]。fn(rng) -> (n, d, X(平らな座標リスト), queries(1-indexed))"""
    out = []
    for d in range(1, MAX_D + 1):
        for kind, n_max, points, q_max in CORRECTNESS_SPEC:
            n = max(2, min(n_max, C // d))
            out.append(("correctness", "c%02d_%s" % (d, kind), _case(d, n, points, q_max and min(n, q_max))))
    for d in range(1, MAX_D + 1):
        dist, ratio = SCORE_SPEC[d]
        n = C // d
        out.append(("score", "d%02d" % d, _case(d, n, DISTRIBUTIONS[dist], max(1, min(n, int(n * ratio))))))
    return out


def make(name, fn):
    return fn(random.Random(zlib.crc32(name.encode())))


def format_input(n, d, X, queries):
    lines = ["%d %d" % (n, d)]
    lines.extend(" ".join(map(str, X[i * d:(i + 1) * d])) for i in range(n))
    lines.append(str(len(queries)))
    lines.extend(map(str, queries))
    return "\n".join(lines) + "\n"
