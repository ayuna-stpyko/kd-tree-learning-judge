#!/usr/bin/env bash
# ジャッジを起動する (自分のユーザで。sudo は不要)。
#   ./start.sh               バックグラウンドで起動する (動いていれば再起動)。
#                            ターミナルや SSH を閉じても止まらない。マシンを再起動すると止まる。
#   ./start.sh --foreground  このターミナルで直接動かす (動作確認用。Ctrl+C で停止)
# ログ: data/judge.log    停止: ./stop.sh
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(pwd)"

if [ ! -f config.ini ]; then
  cp config.example.ini config.ini
  echo "config.ini を作成しました。必要なら編集してください。"
fi
cfg() { python3 -m judge.config "$@"; }

if [ "$(cfg judge backend)" = "docker" ]; then
  if ! docker info >/dev/null 2>&1; then
    echo "Docker に接続できません。docker グループに入っているか (id -nG)、ログインし直したかを確認してください。"
    exit 1
  fi
  IMAGE="$(cfg judge image)"
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "サンドボックスのイメージ ($IMAGE) を作ります..."
    docker build --pull -t "$IMAGE" sandbox
  fi
fi

# テストケースが無い問題だけ生成する (作り直すときは problems/<問題>/tests を消してから起動する)
IFS=', ' read -r -a PROBLEM_DIRS <<< "$(cfg judge problems)"
for PROBLEM_DIR in "${PROBLEM_DIRS[@]}"; do
  [ -n "$PROBLEM_DIR" ] || continue
  if [ ! -f "$PROBLEM_DIR/tests/manifest.json" ]; then
    echo "テストケースを生成します ($PROBLEM_DIR/tests)..."
    if [ "$(cfg judge backend)" = "docker" ]; then
      # PyPy で生成すると速い
      docker run --rm --user "$(id -u):$(id -g)" -v "$REPO/problems:/problems" -w / "$(cfg judge image)" \
        pypy3 problems/lib/make_tests.py "$PROBLEM_DIR"
    else
      python3 problems/lib/make_tests.py "$PROBLEM_DIR"
    fi
  fi
done

mkdir -p data submissions

if [ "${1:-}" = "--foreground" ]; then
  exec python3 -m judge
fi

./stop.sh --quiet
setsid nohup python3 -m judge >> data/judge.log 2>&1 < /dev/null &
echo $! > data/judge.pid

PORT="$(cfg server port)"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null; then
    echo "起動しました。順位表: http://<このマシンの 10.24 のアドレス>:$PORT/"
    echo "ログ: tail -f data/judge.log    停止: ./stop.sh"
    exit 0
  fi
  if ! kill -0 "$(cat data/judge.pid)" 2>/dev/null; then break; fi
  sleep 0.5
done
echo "起動できませんでした。data/judge.log の最後:"
tail -20 data/judge.log
exit 1
