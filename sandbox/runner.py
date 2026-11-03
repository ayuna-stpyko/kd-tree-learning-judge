"""サンドボックス (コンテナ) の中で提出コードを各ケースに対して実行し、時間を計測する。

ホスト側 (judge/sandbox.py) から起動される。結果は 1 行 1 JSON で標準出力に書く。
正解ファイルはここには渡されない。出力の比較はホスト側で行う。

    runner.py --src /sub/main.py --cases /cases --out /out --interp pypy3 \
              --time-limit 2.0 --output-limit-mb 16 [--drop-uid 65534] NAME...

出力する JSON:
    {"type": "compile", "ok": true}
    {"type": "compile", "ok": false, "message": "SyntaxError: ... (line 3)"}
    {"type": "compile", "ok": false, "memory": true}   (構文チェック中にメモリ上限)
    {"type": "start", "name": ...}
    {"type": "case", "name": ..., "time": 秒, "timeout": bool, "exit": 終了コード or null,
     "signal": シグナル番号 or null, "maxrss_kb": int, "stderr_tail": str}
"""
import argparse
import json
import os
import resource
import signal
import subprocess
import sys
import threading
import time

MB = 1024 * 1024
OOM_SCORE_ADJ_MAX = 1000  # OOM killer に最優先で選ばせる値
COMPILE_TIMEOUT_SEC = 10
EXIT_COMPILE_ERROR = 3  # 構文チェック用プロセスが構文エラーを知らせる終了コード
COMPILE_MESSAGE_MAX_CHARS = 500
STDERR_TAIL_BYTES = 4000  # ホストに返す stderr の末尾 (例外の型名を取り出すのに使う)


def kill_group(pid):
    """提出コードのプロセスグループ (子プロセスを含む) をまとめて止める。"""
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


# 構文チェック用プロセスのコード。引数: ファイル, 構文エラーのときの終了コード
COMPILE_CHECK = r"""
import sys
EXIT_COMPILE_ERROR = int(sys.argv[2])
try:
    with open(sys.argv[1], "rb") as f:
        compile(f.read(), "main.py", "exec")
except SyntaxError as e:
    sys.stderr.write("%s: %s (line %s)" % (type(e).__name__, e.msg, e.lineno))
    sys.exit(EXIT_COMPILE_ERROR)
except (ValueError, UnicodeDecodeError) as e:
    sys.stderr.write("%s: %s" % (type(e).__name__, e))
    sys.exit(EXIT_COMPILE_ERROR)
"""


def make_preexec(args, fsize=None):
    def pre():
        os.setsid()
        # メモリ不足のときは runner ではなく提出コードの方が OOM killer に選ばれるようにする
        try:
            with open("/proc/self/oom_score_adj", "w") as f:
                f.write(str(OOM_SCORE_ADJ_MAX))
        except OSError:
            pass
        if fsize is not None:
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if args.drop_uid is not None:
            os.setgroups([])
            os.setgid(args.drop_uid)
            os.setuid(args.drop_uid)
    return pre


MEMORY = object()  # 構文チェック中にメモリ上限で止められた


def check_compile(args):
    """構文チェック。コンパイル時の定数畳み込み (例: b"a" * 10**10) で runner 自身が
    メモリを使い切らないよう、権限を落とした別プロセスで行う。"""
    p = subprocess.Popen([args.interp, "-c", COMPILE_CHECK, args.src, str(EXIT_COMPILE_ERROR)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, preexec_fn=make_preexec(args),
                         close_fds=True, cwd=args.workdir)
    try:
        _, err = p.communicate(timeout=COMPILE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        kill_group(p.pid)
        p.communicate()
        return "compile check timed out"
    if p.returncode == 0:
        return None
    if p.returncode == EXIT_COMPILE_ERROR:
        return err.decode("utf-8", "replace")[:COMPILE_MESSAGE_MAX_CHARS]
    if p.returncode == -signal.SIGKILL:
        return MEMORY
    return "compile check failed (exit %s)" % p.returncode


def run_case(args, name):
    inp = open(os.path.join(args.cases, name + ".in"), "rb")
    out = open(os.path.join(args.out, name + ".out"), "wb")
    err = open(os.path.join(args.out, name + ".err"), "wb")
    fsize = args.output_limit_mb * MB
    pre = make_preexec(args, fsize)

    timed_out = [False]
    t0 = time.perf_counter()
    p = subprocess.Popen([args.interp, args.src], stdin=inp, stdout=out, stderr=err,
                         preexec_fn=pre, close_fds=True, cwd=args.workdir)

    def kill():
        timed_out[0] = True
        kill_group(p.pid)

    timer = threading.Timer(args.time_limit, kill)
    timer.start()
    # Popen.wait(timeout) はポーリングで終了の検知が遅れるので、wait4 で待つ
    _, status, ru = os.wait4(p.pid, 0)
    elapsed = time.perf_counter() - t0
    timer.cancel()
    p.returncode = 0  # Popen 側で再度 wait しないようにする
    kill_group(p.pid)  # 子プロセスが残っていれば片付ける
    for f in (inp, out, err):
        f.close()

    with open(os.path.join(args.out, name + ".err"), "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - STDERR_TAIL_BYTES))
        tail = f.read().decode("utf-8", "replace")

    return {
        "type": "case",
        "name": name,
        "time": round(elapsed, 4),
        "timeout": timed_out[0] or elapsed > args.time_limit,
        "exit": os.WEXITSTATUS(status) if os.WIFEXITED(status) else None,
        "signal": os.WTERMSIG(status) if os.WIFSIGNALED(status) else None,
        "maxrss_kb": ru.ru_maxrss,
        "stderr_tail": tail,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="/tmp")
    ap.add_argument("--interp", default="pypy3")
    ap.add_argument("--time-limit", type=float, default=2.0)
    ap.add_argument("--output-limit-mb", type=int, default=16)
    ap.add_argument("--drop-uid", type=int, default=None)
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()

    msg = check_compile(args)
    if msg is MEMORY:
        emit({"type": "compile", "ok": False, "memory": True, "message": None})
        return
    if msg is not None:
        emit({"type": "compile", "ok": False, "message": msg})
        return
    emit({"type": "compile", "ok": True})
    for name in args.names:
        # 開始を先に知らせておく (コンテナごと止められたときに、どのケースだったか分かるように)
        emit({"type": "start", "name": name})
        emit(run_case(args, name))


if __name__ == "__main__":
    main()
