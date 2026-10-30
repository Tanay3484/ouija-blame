"""Mine deleted-then-restored lines from local clones into results/cases.jsonl.

python -I scripts/mine_reverts.py rails/rails=data/raw/rails.git kubernetes/kubernetes=data/raw/kubernetes.git
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ouija.evaluation.mine import mine_repo  # noqa: E402


def main(args: list[str]) -> None:
    out = ROOT / "results" / "cases.jsonl"
    existing = {}
    if out.exists():
        for ln in out.read_text(encoding="utf-8").splitlines():
            c = json.loads(ln)
            existing[c["id"]] = c
    limit = 60
    for a in args:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
            continue
        owner_repo, _, repo_dir = a.partition("=")
        cases, stats = mine_repo(str(ROOT / repo_dir), owner_repo, limit=limit)
        print(owner_repo, stats)
        for c in cases:
            existing[c.id] = c.to_dict()
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in existing.values()),
        encoding="utf-8",
    )
    print(f"{len(existing)} cases in {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
