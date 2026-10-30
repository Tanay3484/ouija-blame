"""Print the blind grading sheet: per case, the answer key's reason and every method's evidence, unlabelled.

    python -I scripts/grading_sheet.py > data/cache/grading_sheet.md

Evidence over 400 words is shown as its first 150 words plus every paragraph sharing two or more content
words with the reason (a search, as a reader would do with Ctrl-F). The post states this.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = set(
    """the a an and or of to in on for is it its it's this that be with as by not are was were can from
    at so must has have had they them their than then there which who what when should would could will
    into only also more some any all been being out up over under too very just""".split()
)


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9_]{2,}", text.lower()) if w not in STOP}


def excerpt(text: str, reason: str) -> str:
    if len(text.split()) <= 400:
        return text
    key = words(reason)
    head = " ".join(text.split()[:150])
    paras = [p for p in re.split(r"\n\s*\n", text) if len(words(p) & key) >= 2]
    return head + " […]\n\n" + "\n\n[…]\n\n".join(p.strip()[:700] for p in paras[:12])


def main() -> None:
    key = json.loads((ROOT / "results" / "answer_key.json").read_text(encoding="utf-8"))
    cases = {
        c["id"]: c
        for c in map(
            json.loads, (ROOT / "results" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    blind = [
        json.loads(ln)
        for ln in (ROOT / "results" / "grading" / "blind.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    out = sys.stdout
    cur = None
    for item in blind:
        if item["case"] != cur:
            cur = item["case"]
            c = cases[cur]
            out.write(f"\n\n## {cur}\n`{c['line_text'].strip()[:150]}` in `{c['path']}`\n")
            out.write(f"**Answer:** {key[cur]['reason']}\n")
        ev = excerpt(item["evidence"], key[cur]["reason"]) or "(nothing)"
        out.write(f"\n### {item['gid']}\n{ev}\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
