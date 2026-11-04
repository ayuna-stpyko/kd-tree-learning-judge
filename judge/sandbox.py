"""runner.py をサンドボックスで起動する。

docker: 本番用。ネットワークなし・メモリ/CPU/プロセス数の制限・読み取り専用のファイルシステムで、
        提出コードは nobody ユーザで動く。
local : 開発用。隔離なしでこのマシン上で直接動かす。
"""
import os
import signal
import subprocess
import sys

from .config import ROOT

RUNNER = os.path.join(ROOT, "sandbox", "runner.py")
NOBODY_UID = 65534  # 提出コードを動かすユーザ (nobody)
PIDS_LIMIT = 64  # コンテナ内のプロセス・スレッド数の上限 (fork 爆弾対策)
TMPFS_MB = 64  # 提出コードの作業ディレクトリ /tmp の大きさ


class Run:
    def __init__(self, proc, container=None):
        self.proc = proc
        self.container = container

    def lines(self):
        for line in self.proc.stdout:
            yield line

    def kill(self):
        if self.container:
            subprocess.run(["docker", "kill", self.container], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except OSError:
            pass

    def wait(self):
        self.proc.wait()
        err = self.proc.stderr.read()
        self.proc.stdout.close()
        self.proc.stderr.close()
        return self.proc.returncode, err


def start(cfg, p, work, names, cpu, tag):
    """p: 問題。work: sub/main.py, cases/*.in, out/ を持つ作業ディレクトリ。"""
    common = ["--time-limit", str(p.time_limit), "--output-limit-mb", str(p.output_limit_mb)]
    if cfg.backend == "docker":
        container = "kdjudge-%s" % tag
        # 前回の異常終了で同名のコンテナが残っていれば消す
        subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd = [
            "docker", "run", "--rm", "--name", container,
            "--network", "none",
            "--cpuset-cpus", cpu, "--cpus", "1",
            "--memory", "%dm" % p.memory_mb, "--memory-swap", "%dm" % p.memory_mb,
            "--pids-limit", str(PIDS_LIMIT),
            "--read-only", "--tmpfs", "/tmp:rw,size=%dm,mode=1777" % TMPFS_MB,
            "--cap-drop", "ALL", "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "KILL",
            "--security-opt", "no-new-privileges",
            "--user", "0:0",
            "-v", "%s:/runner/runner.py:ro" % RUNNER,
            "-v", "%s:/sub:ro" % os.path.join(work, "sub"),
            "-v", "%s:/cases:ro" % os.path.join(work, "cases"),
            "-v", "%s:/out:rw" % os.path.join(work, "out"),
            cfg.image,
            cfg.interpreter, "/runner/runner.py",
            "--src", "/sub/main.py", "--cases", "/cases", "--out", "/out", "--workdir", "/tmp",
            "--interp", cfg.interpreter, "--drop-uid", str(NOBODY_UID),
        ] + common + ["--"] + names
    else:
        container = None
        cmd = [
            sys.executable, RUNNER,
            "--src", os.path.join(work, "sub", "main.py"), "--cases", os.path.join(work, "cases"),
            "--out", os.path.join(work, "out"), "--workdir", os.path.join(work, "out"),
            "--interp", cfg.interpreter,
        ] + common + ["--"] + names
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    return Run(proc, container)
