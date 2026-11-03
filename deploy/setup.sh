#!/usr/bin/env bash
# ジャッジサーバ (Ubuntu 22.04) の初回セットアップ。運営者のアカウントから sudo で実行する:
#   sudo deploy/setup.sh
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "sudo deploy/setup.sh で実行してください"; exit 1; fi
OPERATOR="${SUDO_USER:?sudo から実行してください}"
cd "$(dirname "$0")/.."

echo "== Docker"
if ! command -v docker >/dev/null; then
  apt-get update
  apt-get install -y docker.io
fi
systemctl enable --now docker
usermod -aG docker "$OPERATOR"

echo "== ログアウト後もユーザサービス (ジャッジ) を動かし続ける"
loginctl enable-linger "$OPERATOR"

echo "== サンドボックスのイメージ (PyPy)"
docker build --pull -t kdjudge-sandbox sandbox
docker run --rm kdjudge-sandbox pypy3 --version

echo "== CPU のクロック制御を performance に固定 (時間計測を安定させる)"
if apt-get install -y linux-tools-common "linux-tools-$(uname -r)" >/dev/null 2>&1; then
  cpupower frequency-set -g performance || true
else
  echo "cpupower を入れられませんでした。必要なら手動で設定してください。"
fi

cat <<MSG

セットアップが終わりました。

次の作業:
  1. いったんログアウトしてログインし直す (docker グループを有効にするため)
  2. ./start.sh で起動する
  3. python3 tools/selftest.py で動作を確認する

ファイアウォール (ufw) を使う場合の例 (SSH を先に許可してから有効にすること):
  sudo ufw allow OpenSSH
  sudo ufw allow from 10.24.0.0/16 to any port 8000 proto tcp
  sudo ufw enable

時間計測をさらに安定させる場合 (任意):
  - ターボブーストを無効にする
  - /etc/default/grub の GRUB_CMDLINE_LINUX に isolcpus=2,3 を足して update-grub し、再起動する
    (config.ini の worker_cpus と合わせる)
  - cpupower の設定は再起動で戻るので、必要なら起動時に実行されるようにする
MSG
