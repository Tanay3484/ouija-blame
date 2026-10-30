"""Local clones of public repos for live séances: plain `git clone` over HTTPS, no token.

Only repos under the size cap are cloned; the oldest clone is removed when there are more than `keep`.
"""

from __future__ import annotations

import re
import shutil
import threading
import time
from pathlib import Path

from .gitwalk import GitError, git

_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class CloneRefused(Exception):
    """Bad name, or too big to clone here."""


def _lock(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def ensure(root: str, owner: str, repo: str, ref: str, size_kb: int | None, cap_kb: int, keep: int, timeout: float) -> str:
    if not (_NAME.match(owner) and _NAME.match(repo)) or owner.startswith(".") or repo.startswith("."):
        raise CloneRefused("That does not look like a GitHub owner and repo.")
    if size_kb is None or size_kb > cap_kb:
        raise CloneRefused(
            f"This repo is {size_kb or '?'} KB; live séances take repos up to {cap_kb // 1000} MB. "
            "The gallery has séances on Kubernetes and Rails."
        )
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{owner}__{repo}.git"
    with _lock(str(path)):
        if not path.exists():
            _evict(base, keep)
            tmp = path.with_suffix(".tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            git(str(base), "clone", "--bare", "--quiet", f"https://github.com/{owner}/{repo}.git", str(tmp), timeout=timeout)
            tmp.rename(path)
        path.touch()
        try:
            git(str(path), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        except GitError:
            git(str(path), "fetch", "--quiet", "origin", ref, timeout=timeout)
    return str(path)


def resolve(repo_dir: str, ref: str) -> str:
    try:
        return git(repo_dir, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    except GitError:
        return git(repo_dir, "rev-parse", "--verify", "FETCH_HEAD^{commit}").strip()


def _evict(base: Path, keep: int) -> None:
    clones = sorted(base.glob("*.git"), key=lambda p: p.stat().st_mtime)
    while len(clones) >= keep:
        shutil.rmtree(clones.pop(0), ignore_errors=True)
    _ = time  # mtime is the clock
