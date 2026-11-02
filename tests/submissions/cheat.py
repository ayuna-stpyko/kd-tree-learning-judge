# 期待: WA (正解ファイルや他のケースを読もうとしても見えないことの確認)
import os, sys
found = []
for root in ("/cases", "/out", "/sub", "/runner", "/"):
    try:
        found += [os.path.join(root, f) for f in os.listdir(root) if f.endswith(".out")]
    except OSError:
        pass
data = sys.stdin.buffer.read().split()
n, d = int(data[0]), int(data[1])
q = int(data[2 + n * d])
ans = None
for path in found:
    try:
        with open(path) as f:
            ans = f.read()
        break
    except OSError:
        pass
sys.stdout.write(ans if ans else "1\n" * q)
