"""入力ファイルが制約を満たすかを確認する。

    python3 validator.py C FILE...
"""
import re
import sys

COORD = 10**8
INT = re.compile(rb"^-?(0|[1-9][0-9]*)$")


def validate(data, C):
    """問題がなければ統計の dict を返し、違反があれば ValueError を投げる。"""
    if not data.endswith(b"\n"):
        raise ValueError("末尾に改行がない")
    lines = data[:-1].split(b"\n")
    pos = 0

    def ints(line, k):
        toks = line.split(b" ")
        if len(toks) != k or not all(INT.match(t) for t in toks):
            raise ValueError("行の形式が不正: %r" % line[:80])
        return [int(t) for t in toks]

    n, d = ints(lines[pos], 2)
    pos += 1
    if not (2 <= n and 1 <= d <= 10 and n * d <= C):
        raise ValueError("N, D が制約外: N=%d D=%d" % (n, d))
    pts = set()
    for _ in range(n):
        p = ints(lines[pos], d)
        pos += 1
        if any(abs(v) > COORD for v in p):
            raise ValueError("座標が範囲外")
        pts.add(tuple(p))
    (q,) = ints(lines[pos], 1)
    pos += 1
    if not (1 <= q <= n):
        raise ValueError("Q が制約外: %d" % q)
    for _ in range(q):
        (i,) = ints(lines[pos], 1)
        pos += 1
        if not (1 <= i <= n):
            raise ValueError("クエリが範囲外: %d" % i)
    if pos != len(lines):
        raise ValueError("余分な行がある")
    return {"N": n, "D": d, "Q": q, "distinct": len(pts), "duplicates": n - len(pts)}


def main():
    C = int(sys.argv[1])
    ok = True
    for path in sys.argv[2:]:
        try:
            with open(path, "rb") as f:
                st = validate(f.read(), C)
            print(path, st)
        except ValueError as e:
            ok = False
            print(path, "NG:", e)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
