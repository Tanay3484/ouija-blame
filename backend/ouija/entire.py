"""Agent-session checkpoints recorded by Entire (https://github.com/entireio/cli), read with plain git.

A commit made with Entire carries an `Entire-Checkpoint: <id>` trailer, and the repo publishes the
session under `refs/entire/checkpoints/<last two chars>/<id>`. Each session folder (`0/`, `1/`, …) holds
`prompt.txt`: what the human asked the agent, which is often the only place the "why" was written.
No Entire account or CLI is needed to read them.
"""

from __future__ import annotations

import json
import re

from .gitwalk import Commit, GitError, git
from .sources import Source

_TRAILER = re.compile(r"^Entire-Checkpoint:\s*([0-9A-Za-z]{8,64})\s*$", re.M)


def checkpoint_ids(message: str) -> list[str]:
    return _TRAILER.findall(message)


def ref_for(cid: str) -> str:
    return f"refs/entire/checkpoints/{cid[-2:]}/{cid}"


def fetch(repo_dir: str, timeout: float = 120.0) -> bool:
    """Fetch the published checkpoint refs. False if the repo has none or the fetch fails."""
    try:
        git(
            repo_dir,
            "fetch",
            "--quiet",
            "origin",
            "refs/entire/checkpoints/*:refs/entire/checkpoints/*",
            timeout=timeout,
        )
        return True
    except GitError:
        return False


def read(repo_dir: str, cid: str) -> list[dict]:
    """The sessions in one checkpoint: [{n, prompt, agent, created}]. Empty if the ref is missing."""
    ref = ref_for(cid)
    try:
        names = git(repo_dir, "ls-tree", "-r", "--name-only", ref).splitlines()
    except GitError:
        return []
    sessions = []
    for n in sorted({p.split("/", 1)[0] for p in names if p.endswith("/prompt.txt")}):
        try:
            prompt = git(repo_dir, "show", f"{ref}:{n}/prompt.txt")
        except GitError:
            continue
        meta: dict = {}
        if f"{n}/metadata.json" in names:
            try:
                meta = json.loads(git(repo_dir, "show", f"{ref}:{n}/metadata.json"))
            except (GitError, ValueError):
                meta = {}
        sessions.append(
            {
                "n": n,
                "prompt": prompt,
                "agent": meta.get("agent") or "an agent",
                "created": meta.get("created_at", ""),
            }
        )
    return sessions


def sources(
    repo_dir: str, commits: list[Commit], owner: str, repo: str, fetched: bool = False
) -> list[Source]:
    """Prompt sources for every commit on the walk that carries a checkpoint trailer."""
    wanted = [(c, cid) for c in commits for cid in checkpoint_ids(c.message)]
    if not wanted:
        return []
    if not fetched:
        fetch(repo_dir)
    out = []
    for c, cid in wanted:
        for s in read(repo_dir, cid):
            out.append(
                Source(
                    id=f"checkpoint:{cid}:{s['n']}",
                    kind="checkpoint",
                    url=f"https://github.com/{owner}/{repo}/commit/{c.sha}",
                    author=c.author,
                    created=s["created"] or c.authored,
                    raw=s["prompt"],
                    title=f"prompt to {s['agent']}, checkpoint {cid}",
                )
            )
    return out
