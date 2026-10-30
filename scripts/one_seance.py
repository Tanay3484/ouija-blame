"""Hold one séance on a local clone, with agent-session checkpoints, and save it for the gallery.

    python -I scripts/one_seance.py <id> <owner/repo> <repo_dir> <ref> <path> <line> "<note>"

Writes results/extra_seances/<id>.json. These are demos, not part of the evaluation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ouija import entire, gitwalk, seance  # noqa: E402
from ouija.config import get_settings  # noqa: E402
from ouija.github import CachedGitHub  # noqa: E402
from ouija.ollama import OllamaClient  # noqa: E402


def main(
    sid: str, owner_repo: str, repo_dir: str, ref: str, path: str, line: str, note: str
) -> None:
    s = get_settings()
    owner, repo = owner_repo.split("/")
    repo_dir = str(ROOT / repo_dir)
    n = int(line)
    commits = gitwalk.walk(repo_dir, ref, path, n)
    extra = entire.sources(repo_dir, commits, owner, repo, fetched=True)
    llm = OllamaClient(
        s.ollama_base,
        s.model,
        timeout_s=s.llm_timeout_s,
        num_predict=s.llm_num_predict,
        num_ctx=s.llm_num_ctx,
    )
    out = seance.run(
        owner=owner,
        repo=repo,
        path=path,
        line=n,
        line_text=gitwalk.line_at(repo_dir, ref, path, n),
        commits=commits,
        github=CachedGitHub(str(ROOT / "data" / "cache" / "github")),
        llm=llm,
        last_seen=gitwalk.last_seen(repo_dir, ref, commits[-1].email),
        extra_sources=extra,
    )
    out["note"] = note
    out["extra_id"] = sid
    out.pop("shown_ids", None)
    d = ROOT / "results" / "extra_seances"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sid}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {k: out[k] for k in ("silent", "quotes", "medium", "stats")},
            indent=1,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main(*sys.argv[1:8])
