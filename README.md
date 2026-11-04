# kd-tree 学習用ジャッジ (運営者向け)

回答者は公開リポジトリ `kd-tree-learning` の `submit.py` で提出する。このリポジトリはジャッジサーバに clone して、運営者のアカウントで動かす。設計の詳細は [PLAN.md](PLAN.md)。

- 標準ライブラリだけで動く (Ubuntu 22.04 の python3 = 3.10 で可。pip は不要)
- 提出コードは Docker のサンドボックスで PyPy で実行する

## 初回セットアップ

```bash
git clone <このリポジトリ> kd-tree-learning-judge
cd kd-tree-learning-judge
```

## 起動・停止

```bash
./start.sh
```

- 初回は `config.ini` (`config.example.ini` のコピー)、サンドボックスのイメージ (`kdjudge-sandbox`、PyPy)、テストケースを作ってから起動する。
- バックグラウンドで動くので、ターミナルや SSH を閉じても止まらない。マシンを再起動すると止まるので、そのときは `./start.sh` し直す。
- 動いていれば再起動する (`git pull` の後もこれでよい)。
- `./start.sh --foreground` でターミナルで直接動かせる (Ctrl+C で停止)。

```bash
./stop.sh
```

ログは `tail -f data/judge.log` で見る。

## 動作確認

```bash
python3 tools/selftest.py
```

判定が分かっている提出 (AC / WA / TLE / RE / CE / OLE / MLE / 正解ファイルの盗み見) を送り、期待どおりの判定になるかを確認する。名前は `_selftest_...` で、`_` で始まる名前は順位表に載らない。AC の結果には次元ごとの時間が出る。

## 設定 (`config.ini`)

| 項目 | 内容 |
|---|---|
| `[server] host` | 待ち受けるアドレス (既定 `0.0.0.0`)。10.24 側のアドレスに絞ってもよい |
| `[server] port` | ポート (既定 8000) |
| `[server] allowed_networks` | 接続を許可するネットワーク (既定 `10.24.0.0/16, 127.0.0.0/8`) |
| `[judge] backend` | `docker` (本番) / `local` (開発用。隔離なしでこのマシンの python で実行) |
| `[judge] worker_cpus` | ワーカーを固定する CPU コア。個数がワーカー数 (既定 `2, 3`) |
| `[judge] rate_limit_seconds` | 同じ名前で続けて提出できるまでの秒数 (既定 30) |

変更したら `./start.sh` で再起動する。

## テストケース

`problems/kdtree-nn/tests/` に生成する (`.gitignore` 済み)。`start.sh` が無ければ自動で生成する。作り直すとき:

```bash
rm -rf problems/kdtree-nn/tests
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/problems/kdtree-nn:/p" -w /p kdjudge-sandbox pypy3 make_tests.py
./start.sh
```

- 正解は参照解 (`reference.py`) で作り、全探索解 (`brute.py`) で検算する。
- 入力の大きさ (N×D の上限) は `problems/kdtree-nn/problem.json` の `max_nd`。
- スコア用ケースの Q は `problems/kdtree-nn/gen.py` の `SCORE_SPEC` (N に対する比率)。
  **ジャッジサーバで `tools/selftest.py` を実行し、ac の次元ごとの時間が各 0.3〜0.5 秒程度になるように調整する。**
- テストケースを変えたら、`tools/rejudge.py --all-ac` で AC の提出を判定し直すと順位表がそろう。

## 提出を見る

提出コードと判定結果は `submissions/<名前>/<提出ID>.py` と `.json` にある (`.gitignore` 済み)。

```bash
tools/show.py              # 名前ごとの提出数・最良スコア
tools/show.py alice        # alice の提出一覧
tools/show.py alice 31     # 提出 31 のコードと判定結果
tools/rejudge.py 31 32     # 判定し直す
```

## 注意

- **`git clean -fdx` は使わない。** `submissions/` と `data/` (DB) が消える。
- 別の場所に clone し直すときは、`submissions/` と `data/` を新しい clone にコピーする。バックアップもこの 2 つをコピーすればよい。

## 構成

```
judge/          ジャッジ本体 (python3 -m judge)
  server.py       HTTP: 提出の受付・結果・順位表
  worker.py       待ち行列から取り出して判定する
  sandbox.py      Docker の起動
  db.py           SQLite (data/judge.db)
  leaderboard.py  順位表
sandbox/        Dockerfile と runner.py (コンテナ内で実行・時間計測)
problems/kdtree-nn/  問題設定・生成器・参照解・全探索解・validator
tests/submissions/   selftest 用の提出
tools/          selftest / show / rejudge / bench_size
```
