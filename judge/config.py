import configparser
import ipaddress
import json
import os
from dataclasses import dataclass, field
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Problem:
    path: str
    title: str
    time_limit: float
    memory_mb: int
    output_limit_mb: int
    max_nd: int
    cases: List[dict] = field(default_factory=list)  # manifest.json の cases

    def tests_dir(self, phase):
        return os.path.join(self.path, "tests", phase)


@dataclass
class Config:
    host: str
    port: int
    allowed_networks: list
    backend: str
    image: str
    interpreter: str
    worker_cpus: List[str]
    problem: Problem
    rate_limit_seconds: int
    max_source_bytes: int
    data_dir: str
    submissions_dir: str

    def allowed(self, ip):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.version == 6 and addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        return any(addr in net for net in self.allowed_networks)


def load_problem(path):
    with open(os.path.join(path, "problem.json")) as f:
        p = json.load(f)
    manifest = os.path.join(path, "tests", "manifest.json")
    if not os.path.exists(manifest):
        raise SystemExit("テストケースがありません。先に python3 %s を実行してください。"
                         % os.path.relpath(os.path.join(path, "make_tests.py"), ROOT))
    with open(manifest) as f:
        m = json.load(f)
    return Problem(path=path, title=p["title"], time_limit=float(p["time_limit_sec"]),
                   memory_mb=int(p["memory_limit_mb"]), output_limit_mb=int(p["output_limit_mb"]),
                   max_nd=int(m["max_nd"]), cases=m["cases"])


def load(path=None):
    path = path or os.path.join(ROOT, "config.ini")
    cp = configparser.ConfigParser()
    if not cp.read(path, encoding="utf-8"):
        raise SystemExit("設定ファイルがありません: %s (config.example.ini をコピーしてください)" % path)
    s, j = cp["server"], cp["judge"]
    nets = [ipaddress.ip_network(x.strip(), strict=False)
            for x in s.get("allowed_networks", "").split(",") if x.strip()]
    problem_path = os.path.join(ROOT, j.get("problem", "problems/kdtree-nn"))
    return Config(
        host=s.get("host", "0.0.0.0"),
        port=s.getint("port", 8000),
        allowed_networks=nets,
        backend=j.get("backend", "docker"),
        image=j.get("image", "kdjudge-sandbox"),
        interpreter=j.get("interpreter", "pypy3"),
        worker_cpus=[x.strip() for x in j.get("worker_cpus", "2,3").split(",") if x.strip()],
        problem=load_problem(problem_path),
        rate_limit_seconds=j.getint("rate_limit_seconds", 30),
        max_source_bytes=j.getint("max_source_bytes", 65536),
        data_dir=os.path.join(ROOT, "data"),
        submissions_dir=os.path.join(ROOT, "submissions"),
    )
