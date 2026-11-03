# 期待: OLE (出力上限 16MB を超える)
import sys
chunk = "9" * (1 << 20)
for _ in range(40):
    sys.stdout.write(chunk)
