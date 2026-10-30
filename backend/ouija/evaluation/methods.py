"""The four methods compared on each case. Each sees only history from before the deletion.

B1 blame          the message of the commit `git blame` shows
B2 blame + PR     B1 plus that commit's PR description, comments, review comments and reviews
B3 log search     the 5 oldest `git log -S<identifier>` commits on the file, messages only
séance            the full walk, PRs and linked issues, read by the medium

Each returns the evidence a person would read, as text, plus the commits it showed.
"""

from __future__ import annotations

from datetime import datetime

from .. import gitwalk, seance
from ..sources import github_sources, parse_time, pr_numbers


def _words(text: str) -> int:
    return len(text.split())


def b1_blame(repo_dir: str, case: dict) -> dict:
    sha = gitwalk.blame(repo_dir, case["parent"], case["path"], case["line"])
    c = gitwalk.show(repo_dir, sha)
    text = c.message
    return {"evidence": text, "words": _words(text), "commits": [c.sha]}


def b2_blame_pr(repo_dir: str, case: dict, github) -> dict:
    owner, repo = case["repo"].split("/")
    sha = gitwalk.blame(repo_dir, case["parent"], case["path"], case["line"])
    c = gitwalk.show(repo_dir, sha)
    nums = pr_numbers([c], github, owner, repo)[c.sha]
    cutoff = parse_time(case["cutoff"])
    srcs = github_sources(nums, github, owner, repo, cutoff)
    # Linked issues are the séance's extra reach; B2 stops at the PR page, as a person clicking through would.
    srcs = [s for s in srcs if s.kind in ("pr", "pr_comment", "review_comment", "review")]
    parts = [c.message] + [f"[{s.kind} by {s.author}] {s.raw}" for s in srcs]
    text = "\n\n".join(parts)
    return {"evidence": text, "words": _words(text), "commits": [c.sha], "prs": nums}


def b3_log_s(repo_dir: str, case: dict) -> dict:
    needle = gitwalk.main_identifier(case["line_text"]) or case["line_text"].strip()
    commits = gitwalk.log_s(repo_dir, case["parent"], case["path"], needle)
    text = "\n\n".join(c.message for c in commits)
    return {
        "evidence": text,
        "words": _words(text),
        "commits": [c.sha for c in commits],
        "needle": needle,
    }


def seance_method(repo_dir: str, case: dict, github, llm, commits=None) -> dict:
    owner, repo = case["repo"].split("/")
    commits = commits or gitwalk.walk(repo_dir, case["parent"], case["path"], case["line"])
    cutoff: datetime = parse_time(case["cutoff"])
    origin = commits[-1]
    try:
        seen = gitwalk.last_seen(repo_dir, case["parent"], origin.email)
    except gitwalk.GitError:
        seen = None
    out = seance.run(
        owner=owner,
        repo=repo,
        path=case["path"],
        line=case["line"],
        line_text=case["line_text"],
        commits=commits,
        github=github,
        llm=llm,
        cutoff=cutoff,
        last_seen=seen,
    )
    if out["silent"]:
        text = seance.SILENCE
    else:
        text = "\n\n".join(f"[{q['kind']} by {q['author']}] {q['text']}" for q in out["quotes"])
    shown = sorted({q["source_id"] for q in out["quotes"]})
    return {
        "evidence": text,
        "words": _words(text),
        "silent": out["silent"],
        "sources": shown,
        "origin": origin.sha,
        "walk": [c.sha for c in commits],
        "seance": out,
    }
