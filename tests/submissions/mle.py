# 期待: MLE (実行中にメモリ上限 1GB を超えて確保する。docker バックエンドのみ)
import sys
n = int("3" + "0" * 9)  # 定数畳み込みされないように実行時に計算する
x = b"a" * n
print(len(x))
