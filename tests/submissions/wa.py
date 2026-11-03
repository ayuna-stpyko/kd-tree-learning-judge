# 期待: WA (常に 1 を出力する)
import sys
data = sys.stdin.buffer.read().split()
n, d = int(data[0]), int(data[1])
q = int(data[2 + n * d])
sys.stdout.write("1\n" * q)
