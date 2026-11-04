"""HTTP サーバ: 提出の受付・結果の返却・順位表。

  POST /api/submit             {"name": ..., "source": ...} -> {"id": ...}
  GET  /api/submissions/<id>   判定の状態と結果
  GET  /api/leaderboard?view=best|all
  GET  /api/board?view=best|all|subs   順位表ページの差し替え部分 (表の HTML) と最近の提出
  GET  /?view=best|all|subs    順位表 (HTML)

提出コードそのものを返す API は無い (運営者はジャッジサーバ上の submissions/ を直接見る)。
"""
import json
import logging
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import db as dbmod
from . import leaderboard
from .common import MB, NAME_MAX_LEN, NAME_RE, VERDICT_NAMES, fmt_time, load_result, submission_path

log = logging.getLogger("judge.server")
MAX_BODY_BYTES = 1 * MB
PUBLIC_CASE_KEYS = ("phase", "index", "d", "verdict", "time")


class BadRequest(Exception):
    def __init__(self, message, status=HTTPStatus.BAD_REQUEST, **extra):
        super().__init__(message)
        self.status = status
        self.extra = extra


def public_status(row):
    """回答者に返してよい情報だけにする (ケースの中身・stderr は返さない)。"""
    out = {"id": row["id"], "name": row["name"], "status": row["status"],
           "submitted_at": fmt_time(row["created_at"])}
    if row["status"] == dbmod.QUEUED:
        out["queue_ahead"] = row.get("queue_ahead", 0)
    elif row["status"] == dbmod.RUNNING and row.get("progress"):
        p = json.loads(row["progress"])
        p.pop("worker", None)
        out["progress"] = p
    elif row["status"] == dbmod.DONE:
        r = load_result(row)
        out.update({
            "verdict": row["verdict"],
            "verdict_name": VERDICT_NAMES.get(row["verdict"], row["verdict"]),
            "score": row["score"],
            "message": r.get("message"),
            "correctness": r.get("correctness"),
            "score_times": r.get("score_times") or {},
            "failed": r.get("failed"),
            "cases": [{k: c[k] for k in PUBLIC_CASE_KEYS} for c in r.get("cases", [])],
        })
    return out


def parse_submission(cfg, raw):
    """POST の本文を検査して (name, source のバイト列) を返す。"""
    try:
        body = json.loads(raw.decode("utf-8"))
        name, source = body["name"], body["source"]
        if not isinstance(name, str) or not isinstance(source, str):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise BadRequest("リクエストが不正です")
    if not NAME_RE.match(name):
        raise BadRequest("名前は英数字と _ - のみ、%d 文字以内にしてください" % NAME_MAX_LEN)
    src = source.encode("utf-8")
    if not src.strip():
        raise BadRequest("ファイルが空です")
    if len(src) > cfg.max_source_bytes:
        raise BadRequest("ファイルが大きすぎます (上限 %d バイト)" % cfg.max_source_bytes)
    return name, src


def make_handler(cfg, db, workers):
    submit_lock = threading.Lock()  # 提出間隔の確認と登録をまとめて行う

    def accept(name, src):
        with submit_lock:
            last = db.last_submit_time(name)
            elapsed = time.time() - last if last is not None else None
            if elapsed is not None and elapsed < cfg.rate_limit_seconds:
                wait = int(cfg.rate_limit_seconds - elapsed) + 1
                raise BadRequest("あと %d 秒待ってから提出してください" % wait,
                                 HTTPStatus.TOO_MANY_REQUESTS, retry_after=wait)
            sid = db.add(name)
            try:
                path = submission_path(cfg.submissions_dir, name, sid, "py")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(src)
            except OSError:
                log.exception("failed to save submission %d", sid)
                db.delete(sid)
                raise BadRequest("提出の保存に失敗しました", HTTPStatus.INTERNAL_SERVER_ERROR)
            db.enqueue(sid)
        workers.notify()
        return sid

    class Handler(BaseHTTPRequestHandler):
        server_version = "kdjudge"

        def log_message(self, fmt, *args):
            log.info("%s %s", self.client_address[0], fmt % args)

        def send(self, status, body, content_type):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, obj, status=HTTPStatus.OK):
            self.send(status, json.dumps(obj, ensure_ascii=False), "application/json")

        def handle_request(self, fn):
            if not cfg.allowed(self.client_address[0]):
                return self.send_json({"error": "このネットワークからは利用できません"}, HTTPStatus.FORBIDDEN)
            try:
                fn(urlparse(self.path))
            except BadRequest as e:
                self.send_json(dict(error=str(e), **e.extra), e.status)

        def do_GET(self):
            self.handle_request(self.get)

        def do_POST(self):
            self.handle_request(self.post)

        def get(self, u):
            view = parse_qs(u.query).get("view", [leaderboard.BEST])[0]
            if view not in leaderboard.VIEWS:
                view = leaderboard.BEST
            if u.path == "/":
                self.send(HTTPStatus.OK, leaderboard.render(cfg, db, view), "text/html")
            elif u.path == "/api/board":
                self.send_json(leaderboard.board(db, view))
            elif u.path == "/api/leaderboard":
                if view == leaderboard.SUBS:
                    view = leaderboard.BEST
                self.send_json({"view": view, "rows": leaderboard.rows(db, view)})
            elif u.path.startswith("/api/submissions/"):
                sid = u.path.rsplit("/", 1)[1]
                row = db.get(int(sid)) if sid.isdigit() else None
                if row is None:
                    raise BadRequest("提出 %s は存在しません" % sid, HTTPStatus.NOT_FOUND)
                self.send_json(public_status(row))
            elif u.path == "/healthz":
                self.send_json({"ok": True})
            else:
                raise BadRequest("not found", HTTPStatus.NOT_FOUND)

        def post(self, u):
            if u.path != "/api/submit":
                raise BadRequest("not found", HTTPStatus.NOT_FOUND)
            length = self.headers.get("Content-Length", "")
            if not length.isdigit() or not 0 < int(length) <= MAX_BODY_BYTES:
                raise BadRequest("リクエストが不正です")
            name, src = parse_submission(cfg, self.rfile.read(int(length)))
            sid = accept(name, src)
            log.info("submission #%d from %s (%s)", sid, name, self.client_address[0])
            self.send_json({"id": sid})

    return Handler


def serve(cfg, db, workers):
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(cfg, db, workers))
    httpd.daemon_threads = True
    log.info("listening on http://%s:%d/", cfg.host, cfg.port)
    httpd.serve_forever()
