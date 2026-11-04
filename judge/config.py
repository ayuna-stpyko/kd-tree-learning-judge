import configparser
import ipaddress
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# config.ini に書かれていない項目の既定値 (config.example.ini と同じ)
DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": "8000", "allowed_networks": "10.24.0.0/16, 127.0.0.0/8"},
    "judge": {"backend": "docker", "image": "kdjudge-sandbox", "interpreter": "pypy3", "worker_cpus": "2, 3",
              "problems": "problems/kdtree-nn, problems/nn-1d, problems/nn-2d-l1", "rate_limit_seconds": "30", "max_source_bytes": "65536"},
}


@dataclass
class Problem:
    id: str  # ディレクトリ名。提出の API で問題を指定するのに使う
    path: str
    title: str
    label: str  # カードなどに出す短い名前
    ranked: bool  # 順位表に載るか (載らない問題は判定だけ返す)
    metric: str
    time_limit: float
    memory_mb: int
    output_limit_mb: int
    max_nd: int
    cases: List[dict] = field(default_factory=list)  # manifest.json の cases

    def case_path(self, case, ext):
        """tests/<phase>/<name><ext> (ext は ".in" か ".out")"""
        return os.path.join(self.path, "tests", case["phase"], case["name"] + ext)


@dataclass
class Config:
    host: str
    port: int
    allowed_networks: list
    backend: str
    image: str
    interpreter: str
    worker_cpus: List[str]
    problems: Dict[str, Problem]  # id -> Problem (config.ini に書いた順)
    rate_limit_seconds: int
    max_source_bytes: int
    data_dir: str
    submissions_dir: str

    @property
    def ranked(self):
        """順位表に載る問題 (ちょうど 1 つ)。API で問題を省略した提出もこの問題になる。"""
        return next(p for p in self.problems.values() if p.ranked)

    @property
    def db_path(self):
        return db_path(self.data_dir)

    def allowed(self, ip):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.version == 6 and addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        return any(addr in net for net in self.allowed_networks)


def db_path(data_dir=os.path.join(ROOT, "data")):
    return os.path.join(data_dir, "judge.db")


def _split(value):
    return [x.strip() for x in value.split(",") if x.strip()]


def load_problem(path):
    with open(os.path.join(path, "problem.json")) as f:
        p = json.load(f)
    manifest = os.path.join(path, "tests", "manifest.json")
    if not os.path.exists(manifest):
        raise SystemExit("テストケースがありません。./start.sh で作るか、python3 problems/lib/make_tests.py %s "
                         "を実行してください。" % os.path.relpath(path, ROOT))
    with open(manifest) as f:
        m = json.load(f)
    return Problem(id=os.path.basename(os.path.normpath(path)), path=path, title=p["title"], label=p["label"],
                   ranked=bool(p["ranked"]), metric=p["metric"], time_limit=float(p["time_limit_sec"]),
                   memory_mb=int(p["memory_limit_mb"]), output_limit_mb=int(p["output_limit_mb"]),
                   max_nd=int(m["max_nd"]), cases=m["cases"])


def load_problems(paths):
    problems = {}
    for path in paths:
        p = load_problem(os.path.join(ROOT, path))
        problems[p.id] = p
    if sum(p.ranked for p in problems.values()) != 1:
        raise SystemExit("problems には順位表に載る問題 (problem.json の ranked が true) をちょうど 1 つ入れてください")
    return problems


def read_ini(path=None):
    path = path or os.path.join(ROOT, "config.ini")
    cp = configparser.ConfigParser()
    cp.read_dict(DEFAULTS)
    if not cp.read(path, encoding="utf-8"):
        raise SystemExit("設定ファイルがありません: %s (config.example.ini をコピーしてください)" % path)
    return cp


def load(path=None):
    cp = read_ini(path)
    s, j = cp["server"], cp["judge"]
    return Config(
        host=s["host"],
        port=s.getint("port"),
        allowed_networks=[ipaddress.ip_network(x, strict=False) for x in _split(s["allowed_networks"])],
        backend=j["backend"],
        image=j["image"],
        interpreter=j["interpreter"],
        worker_cpus=_split(j["worker_cpus"]),
        problems=load_problems(_split(j["problems"])),
        rate_limit_seconds=j.getint("rate_limit_seconds"),
        max_source_bytes=j.getint("max_source_bytes"),
        data_dir=os.path.join(ROOT, "data"),
        submissions_dir=os.path.join(ROOT, "submissions"),
    )


if __name__ == "__main__":
    # シェルスクリプトから設定値を読む: python3 -m judge.config judge backend
    import sys
    print(read_ini()[sys.argv[1]][sys.argv[2]])
