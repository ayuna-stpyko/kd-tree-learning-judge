"""HTTP サーバ: 提出の受付・結果の返却・順位表。

  POST /api/submit             {"name": ..., "source": ...} -> {"id": ...}
  GET  /api/submissions/<id>   判定の状態と結果
  GET  /api/leaderboard?view=best|all
  GET  /?view=best|all         順位表 (HTML)

提出コードそのものを返す API は無い (運営者はジャッジサーバ上の submissions/ を直接見る)。
"""
import json
import logging
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import leaderboard
from .worker import VERDICT_NAMES, submission_path

log = logging.getLogger("judge.server")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MAX_BODY = 1024 * 1024


def public_status(row, problem):
    """回答者に返してよい情報だけにする (ケースの中身・stderr は返さない)。"""
    out = {
        "id": row["id"],
        "name": row["name"],
        "status": row["status"],
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["created_at"])),
    }
    if row["status"] == "queued":
        out["queue_ahead"] = row.get("queue_ahead", 0)
    if row["status"] == "running" and row.get("progress"):
        p = json.loads(row["progress"])
        p.pop("worker", None)
        out["progress"] = p
    if row["status"] == "done":
        r = json.loads(row["result"]) if row["result"] else {}
        out["verdict"] = row["verdict"]
        out["verdict_name"] = VERDICT_NAMES.get(row["verdict"], row["verdict"])
        out["score"] = row["score"]
        out["message"] = r.get("message")
        out["correctness"] = r.get("correctness")
        out["score_times"] = r.get("score_times") or {}
        out["failed"] = r.get("failed")
        out["cases"] = [{k: c[k] for k in ("phase", "index", "d", "verdict", "time")}
                        for c in r.get("cases", [])]
    return out


def make_handler(cfg, db, workers):
    submit_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "kdjudge"

        def log_message(self, fmt, *args):
            log.info("%s %s", self.client_address[0], fmt % args)

        def send_json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_html(self, code, html):
            body = html.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def check_ip(self):
            if cfg.allowed(self.client_address[0]):
                return True
            self.send_json(403, {"error": "このネットワークからは利用できません"})
            return False

        def do_GET(self):
            if not self.check_ip():
                return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            view = qs.get("view", ["best"])[0]
            if view not in ("best", "all"):
                view = "best"
            if u.path == "/":
                rows = leaderboard.rows(db, view)
                self.send_html(200, leaderboard.render(cfg, rows, view))
            elif u.path == "/api/leaderboard":
                self.send_json(200, {"view": view, "rows": leaderboard.rows(db, view)})
            elif u.path.startswith("/api/submissions/"):
                try:
                    sid = int(u.path.rsplit("/", 1)[1])
                except ValueError:
                    return self.send_json(404, {"error": "not found"})
                row = db.get(sid)
                if row is None:
                    return self.send_json(404, {"error": "提出 %d は存在しません" % sid})
                self.send_json(200, public_status(row, cfg.problem))
            elif u.path == "/healthz":
                self.send_json(200, {"ok": True})
            else:
                self.send_json(404, {"error": "not found"})

        def do_POST(self):
            if not self.check_ip():
                return
            if urlparse(self.path).path != "/api/submit":
                return self.send_json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY:
                return self.send_json(400, {"error": "リクエストが不正です"})
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                name = body["name"]
                source = body["source"]
                assert isinstance(name, str) and isinstance(source, str)
            except Exception:
                return self.send_json(400, {"error": "リクエストが不正です"})
            if not NAME_RE.match(name):
                return self.send_json(400, {"error": "名前は英数字と _ - のみ、32 文字以内にしてください"})
            src = source.encode("utf-8")
            if not src.strip():
                return self.send_json(400, {"error": "ファイルが空です"})
            if len(src) > cfg.max_source_bytes:
                return self.send_json(400, {"error": "ファイルが大きすぎます (上限 %d バイト)" % cfg.max_source_bytes})

            with submit_lock:
                last = db.last_submit_time(name)
                now = time.time()
                if last is not None and now - last < cfg.rate_limit_seconds:
                    wait = int(cfg.rate_limit_seconds - (now - last)) + 1
                    return self.send_json(429, {"error": "あと %d 秒待ってから提出してください" % wait,
                                                "retry_after": wait})
                sid = db.add(name)
                try:
                    os.makedirs(os.path.join(cfg.submissions_dir, name), exist_ok=True)
                    with open(submission_path(cfg, name, sid, "py"), "wb") as f:
                        f.write(src)
                except OSError:
                    log.exception("failed to save submission %d", sid)
                    db.delete(sid)
                    return self.send_json(500, {"error": "提出の保存に失敗しました"})
                db.enqueue(sid)
            workers.notify()
            log.info("submission #%d from %s (%s)", sid, name, self.client_address[0])
            self.send_json(200, {"id": sid})

    return Handler


def serve(cfg, db, workers):
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(cfg, db, workers))
    httpd.daemon_threads = True
    log.info("listening on http://%s:%d/", cfg.host, cfg.port)
    httpd.serve_forever()
