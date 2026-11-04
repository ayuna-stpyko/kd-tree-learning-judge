#!/usr/bin/env bash
# ジャッジを停止する。判定中だった提出は、次の起動時に判定し直す。
#   ./stop.sh [--quiet]
set -euo pipefail
cd "$(dirname "$0")"
PIDFILE=data/judge.pid
say() { [ "${1:-}" = "--quiet" ] || echo "$2"; }

PID="$(cat "$PIDFILE" 2>/dev/null || true)"
# PID が使い回されていないか、コマンドラインで確かめる
if [ -z "$PID" ] || ! tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null | grep -q -- "-m judge"; then
  rm -f "$PIDFILE"
  say "${1:-}" "動いていません。"
  exit 0
fi
kill "$PID"
for _ in $(seq 1 20); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 0.5
done
kill -9 "$PID" 2>/dev/null || true
rm -f "$PIDFILE"
say "${1:-}" "停止しました。"
