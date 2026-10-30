"""Tanay's spot check of the blind grades: 10 random cases, all four pieces of evidence each.

    python -I scripts/spot_check.py make     # writes drafts/spot_check.md (no grades shown)
    python -I scripts/spot_check.py score    # compares Tanay's grades with results/grading/grades.json

In drafts/spot_check.md, replace each `?` with R (gives the revert's reason), E (gives some other written
reason the line exists) or N (no reason).
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from grading_sheet import excerpt  # noqa: E402

SHEET = ROOT / "drafts" / "spot_check.md"


def make() -> None:
    key = json.loads((ROOT / "results" / "answer_key.json").read_text(encoding="utf-8"))
    blind = [
        json.loads(ln)
        for ln in (ROOT / "results" / "grading" / "blind.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    cases = sorted({b["case"] for b in blind})
    pick = sorted(random.Random(31).sample(cases, 10))
    out = [
        "# Spot check: grade each item R, E or N\n",
        "R = gives the revert's reason · E = some other written reason the line exists · N = no reason\n",
    ]
    for c in pick:
        out.append(f"\n## {c}\n**Answer:** {key[c]['reason']}\n")
        for b in [b for b in blind if b["case"] == c]:
            out.append(
                f"\n### {b['gid']}: ?\n\n{excerpt(b['evidence'], key[c]['reason']) or '(nothing)'}\n"
            )
    SHEET.parent.mkdir(exist_ok=True)
    SHEET.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {SHEET.relative_to(ROOT)}: {len(pick)} cases")


def score() -> None:
    mine = dict(re.findall(r"^### (g\d+): ([REN])\b", SHEET.read_text(encoding="utf-8"), re.M))
    theirs = json.loads((ROOT / "results" / "grading" / "grades.json").read_text(encoding="utf-8"))
    agree = sum(1 for g, v in mine.items() if theirs.get(g) == v)
    print(f"Tanay graded {len(mine)} items; agreed with Claude's blind grade on {agree}")
    for g, v in sorted(mine.items()):
        if theirs.get(g) != v:
            print(f"  {g}: Tanay {v}, Claude {theirs.get(g)}")


if __name__ == "__main__":
    {"make": make, "score": score}[sys.argv[1]]()
