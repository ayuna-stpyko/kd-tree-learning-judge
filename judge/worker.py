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
from .common import CORRECTNESS, MB, SCORE, fmt_time, id_str, load_result, submission_path

log = logging.getLogger("judge.worker")

# コンテナ全体の上限時間 = ケース数 × (制限時間 + 余裕) + 起動などの余裕
WATCHDOG_PER_CASE_MARGIN_SEC = 1.0
WATCHDOG_MARGIN_SEC = 60.0
# コンテナの主プロセスが SIGKILL で止められたときの終了コード
EXIT_KILLED = 128 + signal.SIGKILL
# 待ち行列が空のとき、次に確認するまでの秒数 (提出があれば notify ですぐ起きる)
IDLE_POLL_SEC = 1.0
LOG_TAIL_CHARS = 2000

_EXC = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)(:|$)")


def exception_type(stderr_tail):
    """stderr の最後の行から例外の型名だけを取り出す (入力の中身を返さないため)。"""
    lines = stderr_tail.strip().splitlines()
    if not lines:
        return None
    m = _EXC.match(lines[-1].strip())
    return m.group(1).split(".")[-1] if m else None


def classify(problem, ev, out_path, ans_path):
    """runner の 1 ケース分の結果から判定を決める。(verdict, message)"""
    if ev["timeout"]:
        return "TLE", None
    sig = ev.get("signal")
    if sig == signal.SIGXFSZ or os.path.getsize(out_path) >= problem.output_limit_mb * MB:
        return "OLE", None
    exc = exception_type(ev.get("stderr_tail", ""))
    # 時間切れ以外で SIGKILL されるのは、メモリ上限で OOM killer に止められた場合
    if exc == "MemoryError" or sig == signal.SIGKILL:
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


def prepare_workdir(cfg, sid, name):
    """作業ディレクトリ (sub/main.py, cases/*.in, out/) を作る。正解ファイルは置かない。"""
    problem = cfg.problem
    work = os.path.join(cfg.data_dir, "work", id_str(sid))
    shutil.rmtree(work, ignore_errors=True)
    for d in ("sub", "cases", "out"):
        os.makedirs(os.path.join(work, d))
    os.chmod(os.path.join(work, "out"), 0o777)  # コンテナ内の root (権限を絞ってある) が書けるように
    main_py = os.path.join(work, "sub", "main.py")
    shutil.copyfile(submission_path(cfg.submissions_dir, name, sid, "py"), main_py)
    os.chmod(main_py, 0o644)  # nobody が読めるように
    for c in problem.cases:
        src = problem.case_path(c, ".in")
        dst = os.path.join(work, "cases", c["name"] + ".in")
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)
    return work


class Judgement:
    """1 つの提出の判定結果を組み立てる。"""

    def __init__(self, problem):
        self.n = {ph: sum(1 for c in problem.cases if c["phase"] == ph) for ph in (CORRECTNESS, SCORE)}
        self.index = {CORRECTNESS: 0, SCORE: 0}
        self.result = {
            "verdict": None, "score": None, "message": None,
            "correctness": {"total": self.n[CORRECTNESS], "passed": 0},
            "score_times": {},
            "cases": [],
            "failed": None,
        }

    @property
    def decided(self):
        return self.result["verdict"] is not None

    def finish_early(self, verdict, message=None):
        self.result["verdict"] = verdict
        self.result["message"] = message

    def record(self, case, verdict, message=None, time=None, maxrss_kb=None):
        phase = case["phase"]
        self.index[phase] += 1
        entry = {"phase": phase, "index": self.index[phase], "d": case["d"], "name": case["name"],
                 "verdict": verdict, "time": time, "maxrss_kb": maxrss_kb}
        self.result["cases"].append(entry)
        if verdict != "AC":
            self.finish_early(verdict, message)
            self.result["failed"] = {k: entry[k] for k in ("phase", "index", "d", "verdict")}
            self.result["failed"]["message"] = message
        elif phase == CORRECTNESS:
            self.result["correctness"]["passed"] += 1
        else:
            self.result["score_times"][str(case["d"])] = time

    def progress(self):
        """次に実行するケースを表す進み具合 (submit.py の表示用)。"""
        if self.index[CORRECTNESS] < self.n[CORRECTNESS]:
            return {"phase": CORRECTNESS, "done": self.index[CORRECTNESS], "total": self.n[CORRECTNESS]}
        done = self.index[SCORE]
        return {"phase": SCORE, "done": done, "total": self.n[SCORE],
                "d": done + 1 if done < self.n[SCORE] else None}

    def complete(self):
        """最後まで実行できたとき: 全部 AC ならスコアを付ける。"""
        if sum(self.index.values()) == sum(self.n.values()):
            self.result["verdict"] = "AC"
            self.result["score"] = round(sum(self.result["score_times"].values()), 4)
            return True
        return False


def judge(cfg, db, sub, cpu):
    sid = sub["id"]
    problem = cfg.problem
    work = prepare_workdir(cfg, sid, sub["name"])
    by_name = {c["name"]: c for c in problem.cases}
    j = Judgement(problem)

    run = sandbox.start(cfg, work, [c["name"] for c in problem.cases], cpu, id_str(sid))
    watchdog_fired = threading.Event()

    def on_watchdog():
        watchdog_fired.set()
        run.kill()

    limit = len(problem.cases) * (problem.time_limit + WATCHDOG_PER_CASE_MARGIN_SEC) + WATCHDOG_MARGIN_SEC
    watchdog = threading.Timer(limit, on_watchdog)
    watchdog.start()
    pending = None  # 開始したが結果がまだ来ていないケース
    try:
        for line in run.lines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev["type"] == "start":
                pending = by_name[ev["name"]]
            elif ev["type"] == "compile":
                if not ev["ok"]:
                    j.finish_early("MLE" if ev.get("memory") else "CE", ev.get("message"))
                    break
                db.set_progress(sid, j.progress())
            else:
                pending = None
                case = by_name[ev["name"]]
                verdict, msg = classify(problem, ev, os.path.join(work, "out", case["name"] + ".out"),
                                        problem.case_path(case, ".out"))
                j.record(case, verdict, msg, ev["time"], ev.get("maxrss_kb"))
                if j.decided:
                    break
                db.set_progress(sid, j.progress())
    finally:
        run.kill()
        rc, err = run.wait()
        watchdog.cancel()
        shutil.rmtree(work, ignore_errors=True)

    if not j.decided and pending is not None and rc == EXIT_KILLED and not watchdog_fired.is_set():
        # 実行中のケースでコンテナごと強制終了された = メモリ上限 (OOM)
        j.record(pending, "MLE")
    if not j.decided and not j.complete():
        log.error("submission %d: runner が途中で終了 (rc=%s): %s", sid, rc, err[-LOG_TAIL_CHARS:])
        j.finish_early("IE", "judge error")
    return j.result


def save_result_file(cfg, row):
    """submissions/<名前>/<ID>.json に判定結果を書く (運営者が直接見る用)。"""
    result = load_result(row)
    data = {"id": row["id"], "name": row["name"], "submitted_at": fmt_time(row["created_at"]),
            "verdict": row["verdict"], "score": row["score"]}
    for k in ("message", "correctness", "score_times", "failed", "cases"):
        data[k] = result.get(k)
    with open(submission_path(cfg.submissions_dir, row["name"], row["id"], "json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


class Workers:
    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self.wake = threading.Event()

    def start(self):
        for i, cpu in enumerate(self.cfg.worker_cpus):
            threading.Thread(target=self.loop, args=(i, cpu), name="worker-%d" % i, daemon=True).start()

    def notify(self):
        self.wake.set()

    def loop(self, i, cpu):
        log.info("worker %d started (cpu %s, backend %s)", i, cpu, self.cfg.backend)
        while True:
            sub = self.db.claim(i)
            if sub is None:
                self.wake.wait(IDLE_POLL_SEC)
                self.wake.clear()
                continue
            log.info("worker %d: judging #%d (%s)", i, sub["id"], sub["name"])
            try:
                result = judge(self.cfg, self.db, sub, cpu)
            except Exception:
                log.error("submission %d: %s", sub["id"], traceback.format_exc())
                result = {"verdict": "IE", "score": None, "message": "judge error"}
            self.db.finish(sub["id"], result)
            save_result_file(self.cfg, self.db.get(sub["id"]))
            log.info("worker %d: #%d -> %s %s", i, sub["id"], result["verdict"], result.get("score"))
