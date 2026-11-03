#!/usr/bin/env bash
# ジャッジを停止する。判定中だった提出は、次の起動時に判定し直す。
set -euo pipefail
systemctl --user stop kdjudge.service
echo "停止しました。"
