"""A séance: walk → sources → rank → medium → quote check → what the ghost says.

`github` is anything with `.get(path)` returning GitHub REST JSON (or None): a dict from the visitor's
browser in the live app, a disk-cached client in the evaluation.
"""

from __future__ import annotations

import re
from datetime import datetime

from .gitwalk import Commit, main_identifier
from .medium import consult
from .ollama import ChatJSON
from .rank import rank
from .sources import (
    Passage,
    Source,
    commit_sources,
    github_sources,
    issue_paths,
    linked_issues,
    passages,
    pr_numbers,
    pr_paths,
    wanted_paths,
)
from .verify import is_verbatim

SILENCE = "I never wrote down why."
_NOREPLY = re.compile(r"^(?:\d+\+)?([\w-]+)@users\.noreply\.github\.com$", re.I)


def focus(commits: list[Commit], k: int = 5) -> list[Commit]:
    """The commits whose PRs we read: the newest few and, always, the one that first wrote the line."""
    if len(commits) <= k:
        return commits
    return commits[: k - 1] + [commits[-1]]


def plan(commits: list[Commit], github: dict, owner: str, repo: str) -> list[str]:
    """GitHub API paths still missing for a séance (the browser fetches these in rounds)."""
    fc = focus(commits)
    missing = [p for p in wanted_paths(fc, owner, repo) if p not in github]
    if missing:
        return missing
    nums = sorted({n for ns in pr_numbers(fc, github, owner, repo).values() for n in ns})
    need = [p for n in nums for p in pr_paths(n, owner, repo) if p not in github]
    if need:
        return need
    issues: list[int] = []
    for n in nums:
        pr = github.get(f"repos/{owner}/{repo}/pulls/{n}") or {}
        for i in linked_issues(pr.get("body") or "", owner, repo):
            if i not in issues and i not in nums:
                issues.append(i)
    return [p for i in issues for p in issue_paths(i, owner, repo) if p not in github]


def gather(
    commits: list[Commit],
    github: dict,
    owner: str,
    repo: str,
    cutoff: datetime | None = None,
    extra: list[Source] | None = None,
) -> list[Source]:
    fc = focus(commits)
    nums = []
    for ns in pr_numbers(fc, github, owner, repo).values():
        for n in ns:
            if n not in nums:
                nums.append(n)
    return (
        commit_sources(commits, owner, repo)
        + github_sources(nums, github, owner, repo, cutoff)
        + list(extra or [])
    )


def login_of(commit: Commit) -> str | None:
    m = _NOREPLY.match(commit.email or "")
    return m.group(1) if m else None


def run(
    *,
    owner: str,
    repo: str,
    path: str,
    line: int,
    line_text: str,
    commits: list[Commit],
    github: dict,
    llm: ChatJSON,
    cutoff: datetime | None = None,
    last_seen: str | None = None,
    extra_sources: list[Source] | None = None,
    passages_shown: int = 16,
    passages_chosen: int = 3,
) -> dict:
    if not commits:
        raise ValueError("no commits touched this line")
    sources = gather(commits, github, owner, repo, cutoff, extra_sources)
    by_id = {s.id: s for s in sources}
    all_passages: list[Passage] = [p for s in sources for p in passages(s)]
    query = " ".join(filter(None, [line_text, path.rsplit("/", 1)[-1], main_identifier(line_text)]))
    kinds = {s.id: s.kind for s in sources}
    shown = rank(all_passages, query, kinds, limit=passages_shown)

    answer = consult(llm, path, line_text, shown, by_id, max_chosen=passages_chosen)

    origin = commits[-1]
    ghost_names = {origin.author.lower()}
    if login := login_of(origin):
        ghost_names.add(login.lower())
    origin_prs = pr_numbers([origin], github, owner, repo).get(origin.sha, [])
    if origin_prs:
        pr = github.get(f"repos/{owner}/{repo}/pulls/{origin_prs[0]}") or {}
        if (pr.get("user") or {}).get("login"):
            ghost_names.add(pr["user"]["login"].lower())
            login = login or pr["user"]["login"]

    quotes, dropped = [], 0
    for p in answer["chosen"]:
        src = by_id[p.source_id]
        if not is_verbatim(p.text, src.raw):
            dropped += 1
            continue
        quotes.append(
            {
                "text": p.text,
                "author": src.author,
                "kind": src.kind,
                "url": src.url,
                "created": src.created,
                "title": src.title,
                "source_id": src.id,
                "is_ghost": src.author.lower() in ghost_names,
            }
        )
    silent = not quotes
    newest = commits[0]
    return {
        "repo": f"{owner}/{repo}",
        "path": path,
        "line": line,
        "line_text": line_text,
        "ghost": {
            "name": origin.author,
            "login": login,
            "first_wrote": origin.authored,
            "commit": origin.sha,
            "commit_url": f"https://github.com/{owner}/{repo}/commit/{origin.sha}",
            "subject": origin.subject,
            "last_seen": last_seen,
        },
        "blame": {
            "commit": newest.sha,
            "subject": newest.subject,
            "author": newest.author,
            "date": newest.authored,
            "url": f"https://github.com/{owner}/{repo}/commit/{newest.sha}",
        },
        "silent": silent,
        "silence": SILENCE if silent else None,
        "quotes": quotes,
        "medium": "" if silent else answer["medium"],
        "stats": {
            "commits_walked": len(commits),
            "sources": len(sources),
            "passages": len(all_passages),
            "shown_to_model": len(shown),
            "dropped_by_checker": dropped,
            "model_error": answer["error"],
        },
        "shown_ids": [p.id for p in shown],
    }
