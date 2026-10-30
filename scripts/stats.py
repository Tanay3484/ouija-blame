"""Compute every number in the post from results/ alone.

    python -I scripts/stats.py

Reads results/runs/*.jsonl, results/grading/{blind.jsonl,key.json,grades.json}; writes
results/summary.json and results/summary.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ouija.evaluation.stats import METHODS, markdown, summarise  # noqa: E402


def jsonl(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> None:
    res = ROOT / "results"
    runs = {m: jsonl(res / "runs" / f"{m}.jsonl") for m in METHODS}
    g = res / "grading"
    blind = jsonl(g / "blind.jsonl")
    key = json.loads((g / "key.json").read_text(encoding="utf-8"))
    grades = json.loads((g / "grades.json").read_text(encoding="utf-8"))
    s = summarise(runs, blind, key, grades)
    (res / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    md = markdown(s)
    (res / "summary.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
