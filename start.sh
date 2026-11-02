#!/usr/bin/env bash
# ジャッジを起動する (運営者のアカウントで、systemd のユーザサービスとして)。
#   ./start.sh               起動 (動いていれば再起動)
#   ./start.sh --foreground  このターミナルで直接動かす (動作確認用。Ctrl+C で停止)
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(pwd)"

if [ ! -f config.ini ]; then
  cp config.example.ini config.ini
  echo "config.ini を作成しました。必要なら [server] host などを編集してください。"
fi

PROBLEM_DIR="$(python3 -c 'import configparser;c=configparser.ConfigParser();c.read("config.ini");print(c.get("judge","problem",fallback="problems/kdtree-nn"))')"
if [ ! -f "$PROBLEM_DIR/tests/manifest.json" ]; then
  echo "テストケースを生成します ($PROBLEM_DIR/tests)..."
  if docker image inspect kdjudge-sandbox >/dev/null 2>&1; then
    # PyPy で生成すると速い
    docker run --rm --user "$(id -u):$(id -g)" -v "$REPO/$PROBLEM_DIR:/p" -w /p kdjudge-sandbox pypy3 make_tests.py
  else
    python3 "$PROBLEM_DIR/make_tests.py"
  fi
fi

mkdir -p data submissions

if [ "${1:-}" = "--foreground" ]; then
  exec python3 -m judge
fi

mkdir -p "$HOME/.config/systemd/user"
sed "s|@REPO@|$REPO|g" deploy/kdjudge.service > "$HOME/.config/systemd/user/kdjudge.service"
systemctl --user daemon-reload
systemctl --user enable kdjudge.service >/dev/null 2>&1
systemctl --user restart kdjudge.service
sleep 2
systemctl --user --no-pager status kdjudge.service | head -5
PORT="$(python3 -c 'import configparser;c=configparser.ConfigParser();c.read("config.ini");print(c.get("server","port",fallback="8000"))')"
echo
echo "起動しました。順位表: http://<このサーバの 10.24 のアドレス>:$PORT/"
echo "ログ: journalctl --user -u kdjudge -f    停止: ./stop.sh"
