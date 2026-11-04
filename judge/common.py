"""ジャッジのあちこちで使う定義。"""
import json
import os
import re
import time

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

CORRECTNESS = "correctness"
SCORE = "score"
PHASES = (CORRECTNESS, SCORE)
PHASE_NAMES = {CORRECTNESS: "正誤判定", SCORE: "スコア計測"}

NAME_MAX_LEN = 32
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,%d}$" % NAME_MAX_LEN)
HIDDEN_NAME_PREFIX = "_"  # この文字で始まる名前 (動作確認用) は順位表に載せない

ID_DIGITS = 5  # 提出ファイル名の桁数 (00042.py)
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
SHORT_DATETIME_FMT = "%m/%d %H:%M:%S"

MB = 1024 * 1024


def fmt_time(ts, fmt=DATETIME_FMT):
    return time.strftime(fmt, time.localtime(ts))


def id_str(sid):
    return "%0*d" % (ID_DIGITS, sid)


def submission_path(submissions_dir, name, sid, ext):
    """submissions/<名前>/<ID>.<ext>"""
    return os.path.join(submissions_dir, name, "%s.%s" % (id_str(sid), ext))


def load_result(row):
    return json.loads(row["result"]) if row.get("result") else {}
