"""ジャッジを起動する: python3 -m judge [--config config.ini]"""
import argparse
import logging
import os
import subprocess
import sys

from . import config, db, server, worker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stdout)
    log = logging.getLogger("judge")
    cfg = config.load(args.config)
    for d in (cfg.data_dir, os.path.join(cfg.data_dir, "work"), cfg.submissions_dir):
        os.makedirs(d, exist_ok=True)

    if cfg.backend == "docker":
        r = subprocess.run(["docker", "image", "inspect", cfg.image], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            sys.exit("Docker イメージ %s がありません。./start.sh で作ってください。" % cfg.image)
    else:
        log.warning("backend=local: 提出コードを隔離せずに実行します (開発用)")

    for p in cfg.problems.values():
        log.info("problem %s: %s (%d cases, N*D <= %d, TL %.1fs%s)", p.id, p.title, len(p.cases), p.max_nd,
                 p.time_limit, ", 順位表" if p.ranked else "")
    database = db.DB(cfg.db_path, recover=True, legacy_problem=cfg.ranked.id)
    workers = worker.Workers(cfg, database)
    workers.start()
    server.serve(cfg, database, workers)


if __name__ == "__main__":
    main()
