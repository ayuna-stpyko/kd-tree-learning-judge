"""待ち行列から提出を取り出して判定するワーカー。

判定の順番 (PLAN.md 第 5 章):
  1. 構文チェック -> 失敗なら CE
  2. 正誤判定用を順に実行 -> AC 以外が出たらそこで終了
  3. スコア用 d=1..10 を実行 -> AC 以外が出たらそこで終了
  4. 全部 AC -> スコア用の実行時間の和をスコアにする
出力と正解の比較はコンテナの外 (ここ) で行い、計測時間には含めない。
"""
import json
import logging
import os
import re
import shutil
import signal
import threading
import traceback

from . import sandbox

log = logging.getLogger("judge.worker")

VERDICT_NAMES = {
    "AC": "Accepted",
    "WA": "Wrong Answer",
    "TLE": "Time Limit Exceeded",
    "RE": "Runtime Error",
    "MLE": "Memory Limit Exceeded",
    "OLE": "Output Limit Exceeded",
    "CE": "Compile Error",
    "IE": "Internal Error",
}

_EXC = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)(:|$)")


def exception_type(stderr_tail):
    """stderr の最後の行から例外の型名だけを取り出す (入力の中身を返さないため)。"""
    for line in reversed(stderr_tail.strip().splitlines()):
        m = _EXC.match(line.strip())
        if m:
            return m.group(1).split(".")[-1]
        break
    return None


def submission_path(cfg, name, sid, ext):
    return os.path.join(cfg.submissions_dir, name, "%05d.%s" % (sid, ext))


def classify(cfg, ev, out_path, ans_path):
    """runner の 1 ケース分の結果から判定を決める。(verdict, message)"""
    limit = cfg.problem.output_limit_mb * 1024 * 1024
    if ev["timeout"]:
        return "TLE", None
    sig = ev.get("signal")
    if sig == signal.SIGXFSZ or os.path.getsize(out_path) >= limit:
        return "OLE", None
    exc = exception_type(ev.get("stderr_tail", ""))
    if exc == "MemoryError":
        return "MLE", None
    if sig == signal.SIGKILL:
        # 時間切れ以外で SIGKILL されるのは、メモリ上限で OOM killer に止められた場合
        return "MLE", None
    if sig is not None:
        return "RE", "signal %d" % sig
    if ev.get("exit") != 0:
        return "RE", exc or "exit code %s" % ev.get("exit")
    with open(out_path, "rb") as f:
        got = f.read().split()
    with open(ans_path, "rb") as f:
        exp = f.read().split()
    return ("AC", None) if got == exp else ("WA", None)


def judge(cfg, db, sub, cpu):
    sid, name = sub["id"], sub["name"]
    problem = cfg.problem
    work = os.path.join(cfg.data_dir, "work", "%05d" % sid)
    shutil.rmtree(work, ignore_errors=True)
    for d in ("sub", "cases", "out"):
        os.makedirs(os.path.join(work, d))
    os.chmod(os.path.join(work, "out"), 0o777)  # コンテナ内の root (CAP なし) が書けるように
    main_py = os.path.join(work, "sub", "main.py")
    shutil.copyfile(submission_path(cfg, name, sid, "py"), main_py)
    os.chmod(main_py, 0o644)

    cases = problem.cases
    for c in cases:
        src = os.path.join(problem.tests_dir(c["phase"]), c["name"] + ".in")
        dst = os.path.join(work, "cases", c["name"] + ".in")
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)

    by_name = {c["name"]: c for c in cases}
    n_corr = sum(1 for c in cases if c["phase"] == "correctness")
    n_score = len(cases) - n_corr
    index = {"correctness": 0, "score": 0}
    result = {
        "verdict": None, "score": None, "message": None,
        "correctness": {"total": n_corr, "passed": 0},
        "score_times": {},
        "cases": [],
        "failed": None,
    }

    run = sandbox.start(cfg, work, [c["name"] for c in cases], cpu, "%05d" % sid)
    fired = []
    watchdog = threading.Timer(len(cases) * (problem.time_limit + 1) + 60,
                               lambda: (fired.append(True), run.kill()))
    watchdog.start()
    finished = 0
    pending = None  # 開始したが結果がまだ来ていないケース
    try:
        for line in run.lines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev["type"] == "start":
                pending = ev["name"]
                continue
            if ev["type"] == "compile":
                if not ev["ok"]:
                    result["verdict"] = "MLE" if ev.get("memory") else "CE"
                    result["message"] = ev["message"]
                    break
                db.set_progress(sid, {"phase": "correctness", "done": 0, "total": n_corr})
                continue
            pending = None
            c = by_name[ev["name"]]
            phase = c["phase"]
            index[phase] += 1
            verdict, msg = classify(cfg, ev, os.path.join(work, "out", c["name"] + ".out"),
                                    os.path.join(problem.tests_dir(phase), c["name"] + ".out"))
            result["cases"].append({
                "phase": phase, "index": index[phase], "d": c["d"], "name": c["name"],
                "verdict": verdict, "time": ev["time"], "maxrss_kb": ev.get("maxrss_kb"),
            })
            finished += 1
            if verdict != "AC":
                result["verdict"] = verdict
                result["message"] = msg
                result["failed"] = {"phase": phase, "index": index[phase], "d": c["d"],
                                    "verdict": verdict, "message": msg}
                break
            if phase == "correctness":
                result["correctness"]["passed"] += 1
                if index[phase] == n_corr:
                    db.set_progress(sid, {"phase": "score", "done": 0, "total": n_score, "d": 1})
                else:
                    db.set_progress(sid, {"phase": "correctness", "done": index[phase], "total": n_corr})
            else:
                result["score_times"][str(c["d"])] = ev["time"]
                nxt = index[phase] + 1
                db.set_progress(sid, {"phase": "score", "done": index[phase], "total": n_score,
                                      "d": nxt if nxt <= n_score else None})
    finally:
        run.kill()
        rc, err = run.wait()
        watchdog.cancel()

    if result["verdict"] is None and pending is not None and rc == 137 and not fired:
        # 実行中のケースでコンテナごと強制終了された = メモリ上限 (OOM)
        c = by_name[pending]
        index[c["phase"]] += 1
        result["verdict"] = "MLE"
        result["failed"] = {"phase": c["phase"], "index": index[c["phase"]], "d": c["d"],
                            "verdict": "MLE", "message": None}
        result["cases"].append({"phase": c["phase"], "index": index[c["phase"]], "d": c["d"],
                                "name": c["name"], "verdict": "MLE", "time": None, "maxrss_kb": None})
    if result["verdict"] is None:
        if finished == len(cases):
            result["verdict"] = "AC"
            result["score"] = round(sum(result["score_times"].values()), 4)
        else:
            log.error("submission %d: runner が途中で終了 (rc=%s): %s", sid, rc, err[-2000:])
            result["verdict"] = "IE"
            result["message"] = "judge error"
    shutil.rmtree(work, ignore_errors=True)
    return result


class Workers:
    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self.wake = threading.Event()

    def start(self):
        for i, cpu in enumerate(self.cfg.worker_cpus):
            t = threading.Thread(target=self.loop, args=(i, cpu), name="worker-%d" % i, daemon=True)
            t.start()

    def notify(self):
        self.wake.set()

    def loop(self, i, cpu):
        log.info("worker %d started (cpu %s, backend %s)", i, cpu, self.cfg.backend)
        while True:
            sub = self.db.claim(i)
            if sub is None:
                self.wake.wait(1.0)
                self.wake.clear()
                continue
            log.info("worker %d: judging #%d (%s)", i, sub["id"], sub["name"])
            try:
                result = judge(self.cfg, self.db, sub, cpu)
            except Exception:
                log.error("submission %d: %s", sub["id"], traceback.format_exc())
                result = {"verdict": "IE", "score": None, "message": "judge error", "cases": [],
                          "correctness": None, "score_times": {}, "failed": None}
            self.db.finish(sub["id"], result)
            save_result_file(self.cfg, self.db.get(sub["id"]))
            log.info("worker %d: #%d -> %s %s", i, sub["id"], result["verdict"], result.get("score"))


def save_result_file(cfg, row):
    """submissions/<名前>/<ID>.json に判定結果を書く (運営者が直接見る用)。"""
    import time
    result = json.loads(row["result"]) if row.get("result") else {}
    data = {
        "id": row["id"],
        "name": row["name"],
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["created_at"])),
        "verdict": row["verdict"],
        "score": row["score"],
        "message": result.get("message"),
        "correctness": result.get("correctness"),
        "score_times": result.get("score_times"),
        "failed": result.get("failed"),
        "cases": result.get("cases"),
    }
    path = submission_path(cfg, row["name"], row["id"], "json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
