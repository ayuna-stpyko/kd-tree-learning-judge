# 提出コードを実行するサンドボックス。外部ライブラリ (numpy, scipy など) は入れない。
# PyPy のバージョンを上げるときはタグを変えてビルドし直す (deploy/setup.sh)。
ARG PYPY_TAG=3-slim
FROM pypy:${PYPY_TAG}

# runner.py は起動時に読み取り専用でマウントする (judge/sandbox.py)。
# 提出コードは nobody (uid 65534) で動かす。
WORKDIR /tmp
