"""Copy the evaluation's séances into the app's gallery, with what happened after each deletion.

    python -I scripts/build_gallery.py

Reads results/seances/*.json, results/cases.jsonl and results/answer_key.json; writes
app/public/gallery/<case>.json and app/public/gallery/index.json. Séances that found a reason come first.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cases = {
        c["id"]: c
        for c in (
            json.loads(ln)
            for ln in (ROOT / "results" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    key = json.loads((ROOT / "results" / "answer_key.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "app" / "public" / "gallery"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    index = []
    for f in sorted((ROOT / "results" / "seances").glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        cid = s["case"]["id"]
        if cid not in cases or not key.get(cid, {}).get("keep"):
            continue
        c = cases[cid]
        s["revert_subject"] = c["revert_subject"]
        s["answer"] = key[cid]["reason"]
        s.pop("shown_ids", None)
        (out_dir / f"{cid}.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
        g = s["ghost"]
        index.append(
            {
                "id": cid,
                "repo": s["repo"],
                "path": s["path"],
                "line_text": s["line_text"],
                "deletion_subject": c["deletion_subject"],
                "revert_subject": c["revert_subject"],
                "deleted_on": c["cutoff"],
                "ghost": f"@{g['login']}" if g.get("login") else g["name"],
                "silent": s["silent"],
            }
        )
    # Demos outside the evaluation (for example lines written with an agent, read from Entire checkpoints).
    extras = []
    for f in sorted((ROOT / "results" / "extra_seances").glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        sid = s["extra_id"]
        (out_dir / f"{sid}.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
        g = s["ghost"]
        extras.append(
            {
                "id": sid,
                "repo": s["repo"],
                "path": s["path"],
                "line_text": s["line_text"],
                "deletion_subject": s.get("note", ""),
                "revert_subject": "",
                "deleted_on": "",
                "ghost": f"@{g['login']}" if g.get("login") else g["name"],
                "silent": s["silent"],
            }
        )
    order = {"kubernetes/kubernetes": 0, "rails/rails": 1, "home-assistant/core": 2}
    index.sort(key=lambda x: (x["silent"], order.get(x["repo"], 3), x["id"]))
    index = extras + index
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(index)} séances in the gallery ({sum(not x['silent'] for x in index)} speak)")


if __name__ == "__main__":
    main()
