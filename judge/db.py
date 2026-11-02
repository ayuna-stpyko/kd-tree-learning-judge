"""提出の状態を SQLite で管理する。この表がそのまま待ち行列になる。

status: new (受付中) -> queued (待機中) -> running (判定中) -> done (完了)
ジャッジ本体と tools/ (show.py, rejudge.py) の両方から使う。
"""
import json
import sqlite3
import threading
import time

NEW, QUEUED, RUNNING, DONE = "new", "queued", "running", "done"
SQLITE_BUSY_TIMEOUT_SEC = 30

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    created_at  REAL NOT NULL,
    status      TEXT NOT NULL,
    verdict     TEXT,
    score       REAL,
    progress    TEXT,
    result      TEXT,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_status ON submissions(status, id);
CREATE INDEX IF NOT EXISTS idx_name ON submissions(name, created_at);
"""


class DB:
    def __init__(self, path, recover=False):
        """recover=True (ジャッジ本体の起動時): 前回の停止で中断された提出を片付ける。"""
        self.path = path
        if recover:
            def f(c):
                c.executescript(SCHEMA)
                # 判定中だったものは待機中に戻してやり直す
                c.execute("UPDATE submissions SET status=?, progress=NULL WHERE status=?", (QUEUED, RUNNING))
                # ファイルの保存の途中で止まった提出は消す
                c.execute("DELETE FROM submissions WHERE status=?", (NEW,))
            self._run(f)

    def _run(self, fn):
        with _lock:
            c = sqlite3.connect(self.path, timeout=SQLITE_BUSY_TIMEOUT_SEC)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            try:
                with c:
                    return fn(c)
            finally:
                c.close()

    def _exec(self, sql, args=()):
        self._run(lambda c: c.execute(sql, args))

    def _rows(self, sql, args=()):
        return self._run(lambda c: [dict(r) for r in c.execute(sql, args).fetchall()])

    # ---- 受付
    def last_submit_time(self, name):
        return self._run(lambda c: c.execute("SELECT MAX(created_at) FROM submissions WHERE name=?",
                                             (name,)).fetchone()[0])

    def add(self, name):
        # ファイルを保存し終えるまでは NEW にしておき、ワーカーに拾われないようにする
        return self._run(lambda c: c.execute("INSERT INTO submissions(name, created_at, status) VALUES (?, ?, ?)",
                                             (name, time.time(), NEW)).lastrowid)

    def enqueue(self, sid):
        self._exec("UPDATE submissions SET status=? WHERE id=?", (QUEUED, sid))

    def delete(self, sid):
        self._exec("DELETE FROM submissions WHERE id=?", (sid,))

    # ---- ワーカー
    def claim(self, worker):
        """待機中で最も古い提出を判定中にして返す。無ければ None。"""
        def f(c):
            r = c.execute("SELECT * FROM submissions WHERE status=? ORDER BY id LIMIT 1", (QUEUED,)).fetchone()
            if r is None:
                return None
            c.execute("UPDATE submissions SET status=?, progress=? WHERE id=?",
                      (RUNNING, json.dumps({"phase": "prepare", "worker": worker}), r["id"]))
            return dict(r)
        return self._run(f)

    def set_progress(self, sid, progress):
        self._exec("UPDATE submissions SET progress=? WHERE id=?", (json.dumps(progress), sid))

    def finish(self, sid, result):
        self._exec("UPDATE submissions SET status=?, verdict=?, score=?, result=?, progress=NULL, finished_at=? "
                   "WHERE id=?", (DONE, result["verdict"], result.get("score"), json.dumps(result), time.time(), sid))

    def requeue(self, ids):
        """判定済みの提出を待機中に戻す (判定し直し)。"""
        def f(c):
            for sid in ids:
                c.execute("UPDATE submissions SET status=?, verdict=NULL, score=NULL, result=NULL, progress=NULL, "
                          "finished_at=NULL WHERE id=? AND status=?", (QUEUED, sid, DONE))
        self._run(f)

    # ---- 参照
    def get(self, sid):
        def f(c):
            r = c.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
            if r is None:
                return None
            d = dict(r)
            if d["status"] == QUEUED:
                d["queue_ahead"] = c.execute("SELECT COUNT(*) FROM submissions WHERE status=? AND id<?",
                                             (QUEUED, sid)).fetchone()[0]
            return d
        return self._run(f)

    def accepted(self):
        """AC の提出。スコアの昇順、同じなら提出が早い順。"""
        return self._rows("SELECT id, name, created_at, score, result FROM submissions "
                          "WHERE status=? AND verdict='AC' ORDER BY score, created_at", (DONE,))

    def counts_by_name(self):
        return {r["name"]: r["n"] for r in self._rows("SELECT name, COUNT(*) AS n FROM submissions GROUP BY name")}

    def summary_by_name(self):
        """名前ごとの提出数・最良スコア・最終提出時刻。"""
        return self._rows("SELECT name, COUNT(*) AS n, MIN(CASE WHEN verdict='AC' THEN score END) AS best, "
                          "MAX(created_at) AS last FROM submissions GROUP BY name ORDER BY name")

    def by_name(self, name):
        return self._rows("SELECT * FROM submissions WHERE name=? ORDER BY id", (name,))

    def accepted_ids(self):
        return [r["id"] for r in self._rows("SELECT id FROM submissions WHERE verdict='AC' ORDER BY id")]
