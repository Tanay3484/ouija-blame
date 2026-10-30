"""Run the four methods on every case in results/cases.jsonl and write what each one shows.

    python -I scripts/run_eval.py                 # all methods; Gemma through local Ollama
    python -I scripts/run_eval.py --only=seance   # rerun one method
    python -I scripts/run_eval.py --offline       # cached GitHub responses only
    python -I scripts/run_eval.py --missing       # only cases a method has not run yet

Writes results/runs/<method>.jsonl and results/seances/<case>.json (the gallery's source), then the blind
grading file results/grading/blind.jsonl with its key in results/grading/key.json.
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ouija import gitwalk  # noqa: E402
from ouija.config import get_settings  # noqa: E402
from ouija.evaluation import methods  # noqa: E402
from ouija.github import CachedGitHub  # noqa: E402
from ouija.ollama import OllamaClient  # noqa: E402

METHODS = ["b1", "b2", "b3", "seance"]
REPO_DIRS = {
    "rails/rails": "data/raw/rails.git",
    "ansible/ansible": "data/raw/ansible.git",
    "istio/istio": "data/raw/istio.git",
    "kubernetes/kubernetes": "data/raw/kubernetes.git",
    "home-assistant/core": "data/raw/home-assistant.git",
}


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main(args: list[str]) -> None:
    only = next((a.split("=", 1)[1].split(",") for a in args if a.startswith("--only=")), METHODS)
    offline = "--offline" in args
    missing = "--missing" in args  # only cases not yet in a method's file; the rest are kept
    s = get_settings()
    gh = CachedGitHub(str(ROOT / "data" / "cache" / "github"), offline=offline)
    llm = OllamaClient(
        s.ollama_base,
        s.model,
        timeout_s=s.llm_timeout_s,
        num_predict=s.llm_num_predict,
        num_ctx=s.llm_num_ctx,
    )
    cases = load_jsonl(ROOT / "results" / "cases.jsonl")
    key = ROOT / "results" / "answer_key.json"
    if key.exists():
        keep = {k for k, v in json.loads(key.read_text(encoding="utf-8")).items() if v.get("keep")}
        cases = [c for c in cases if c["id"] in keep]
    runs_dir = ROOT / "results" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "seances").mkdir(exist_ok=True)

    for m in only:
        done = {r["case"]: r for r in load_jsonl(runs_dir / f"{m}.jsonl")} if missing else {}
        rows = []
        t0 = time.time()
        for i, c in enumerate(cases, 1):
            if c["id"] in done:
                rows.append(done[c["id"]])
                continue
            repo_dir = str(ROOT / REPO_DIRS[c["repo"]])
            t = time.time()
            try:
                if m == "b1":
                    r = methods.b1_blame(repo_dir, c)
                elif m == "b2":
                    r = methods.b2_blame_pr(repo_dir, c, gh)
                elif m == "b3":
                    r = methods.b3_log_s(repo_dir, c)
                else:
                    r = methods.seance_method(repo_dir, c, gh, llm)
                    out = r.pop("seance")
                    out["case"] = {
                        k: c[k] for k in ("id", "revert", "deletion", "deletion_subject", "cutoff")
                    }
                    (ROOT / "results" / "seances" / f"{c['id']}.json").write_text(
                        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
                    )
                err = None
            except (gitwalk.GitError, ValueError) as e:
                r, err = {"evidence": "", "words": 0, "commits": []}, str(e)[:300]
            rows.append(
                {
                    "case": c["id"],
                    "method": m,
                    "seconds": round(time.time() - t, 1),
                    "error": err,
                    **r,
                }
            )
            print(
                f"[{m}] {i}/{len(cases)} {c['id']} {rows[-1]['seconds']}s {'ERR ' + err if err else ''}",
                flush=True,
            )
        (runs_dir / f"{m}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
        )
        print(f"[{m}] done in {time.time() - t0:.0f}s; {gh.calls} GitHub calls so far", flush=True)

    write_blind()


def write_blind() -> None:
    """Shuffle every method's evidence under random ids, so grading cannot see the method."""
    items = []
    for m in METHODS:
        for r in load_jsonl(ROOT / "results" / "runs" / f"{m}.jsonl"):
            items.append((r["case"], m, r["evidence"]))
    rng = random.Random(20261031)
    rng.shuffle(items)
    gdir = ROOT / "results" / "grading"
    gdir.mkdir(parents=True, exist_ok=True)
    blind, key = [], {}
    for n, (case, m, ev) in enumerate(items, 1):
        gid = f"g{n:03d}"
        blind.append({"gid": gid, "case": case, "evidence": ev})
        key[gid] = m
    blind.sort(
        key=lambda x: (x["case"], x["gid"])
    )  # grade case by case; order within a case is random
    (gdir / "blind.jsonl").write_text(
        "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in blind), encoding="utf-8"
    )
    (gdir / "key.json").write_text(json.dumps(key, indent=0), encoding="utf-8")
    print(f"blind grading file: {len(blind)} items")


if __name__ == "__main__":
    main(sys.argv[1:])
