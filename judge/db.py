"""提出の状態を SQLite で管理する。この表がそのまま待ち行列になる。

status: new (受付中) -> queued (待機中) -> running (判定中) -> done (完了)
"""
import json
import sqlite3
import threading
import time

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
    def __init__(self, path):
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)
            # 前回の停止時に判定中だったものは待機中に戻してやり直す
            c.execute("UPDATE submissions SET status='queued', progress=NULL WHERE status='running'")
            # 保存の途中で止まった提出は消す
            c.execute("DELETE FROM submissions WHERE status='new'")

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _run(self, fn):
        with _lock:
            c = self._conn()
            try:
                with c:
                    return fn(c)
            finally:
                c.close()

    # ---- 受付
    def last_submit_time(self, name):
        def f(c):
            r = c.execute("SELECT MAX(created_at) FROM submissions WHERE name=?", (name,)).fetchone()
            return r[0]
        return self._run(f)

    def add(self, name):
        def f(c):
            # ファイルを保存し終えるまでは 'new' にしておき、ワーカーに拾われないようにする
            cur = c.execute("INSERT INTO submissions(name, created_at, status) VALUES (?, ?, 'new')",
                            (name, time.time()))
            return cur.lastrowid
        return self._run(f)

    def enqueue(self, sid):
        self._run(lambda c: c.execute("UPDATE submissions SET status='queued' WHERE id=?", (sid,)))

    def delete(self, sid):
        self._run(lambda c: c.execute("DELETE FROM submissions WHERE id=?", (sid,)))

    # ---- ワーカー
    def claim(self, worker):
        """待機中で最も古い提出を判定中にして返す。無ければ None。"""
        def f(c):
            r = c.execute("SELECT * FROM submissions WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
            if r is None:
                return None
            c.execute("UPDATE submissions SET status='running', progress=? WHERE id=?",
                      (json.dumps({"phase": "prepare", "worker": worker}), r["id"]))
            return dict(r)
        return self._run(f)

    def set_progress(self, sid, progress):
        self._run(lambda c: c.execute("UPDATE submissions SET progress=? WHERE id=?",
                                      (json.dumps(progress), sid)))

    def finish(self, sid, result):
        self._run(lambda c: c.execute(
            "UPDATE submissions SET status='done', verdict=?, score=?, result=?, progress=NULL, finished_at=? "
            "WHERE id=?",
            (result["verdict"], result.get("score"), json.dumps(result), time.time(), sid)))

    def requeue(self, sid):
        self._run(lambda c: c.execute(
            "UPDATE submissions SET status='queued', verdict=NULL, score=NULL, result=NULL, progress=NULL, "
            "finished_at=NULL WHERE id=?", (sid,)))

    # ---- 参照
    def get(self, sid):
        def f(c):
            r = c.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
            if r is None:
                return None
            d = dict(r)
            if d["status"] == "queued":
                d["queue_ahead"] = c.execute(
                    "SELECT COUNT(*) FROM submissions WHERE status='queued' AND id<?", (sid,)).fetchone()[0]
            return d
        return self._run(f)

    def accepted(self):
        def f(c):
            rows = c.execute("SELECT id, name, created_at, score, result FROM submissions "
                             "WHERE status='done' AND verdict='AC' ORDER BY score, created_at").fetchall()
            return [dict(r) for r in rows]
        return self._run(f)

    def counts_by_name(self):
        def f(c):
            return {r[0]: r[1] for r in c.execute("SELECT name, COUNT(*) FROM submissions GROUP BY name")}
        return self._run(f)

    def all(self, name=None):
        def f(c):
            if name is None:
                rows = c.execute("SELECT * FROM submissions ORDER BY id").fetchall()
            else:
                rows = c.execute("SELECT * FROM submissions WHERE name=? ORDER BY id", (name,)).fetchall()
            return [dict(r) for r in rows]
        return self._run(f)
