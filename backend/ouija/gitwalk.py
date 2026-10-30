"""Walking one line's history with plain git: `git log -L`, `git blame` and `git log -S`.

Everything here reads a local clone. The walk starts at a given ref, so the evaluation can start it at the
parent of a deletion and never see what came after.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass

# Field and record separators that never appear in commit text.
_FS, _RS = "\x1f", "\x1e"
_FORMAT = _FS.join(["%H", "%an", "%ae", "%aI", "%cI", "%s", "%b"]) + _RS


class GitError(Exception):
    """git failed, timed out, or the ref, path or line does not exist."""


@dataclass(frozen=True)
class Commit:
    sha: str
    author: str
    email: str
    authored: str  # ISO 8601
    committed: str
    subject: str
    body: str

    @property
    def message(self) -> str:
        return f"{self.subject}\n\n{self.body}".strip()

    def to_dict(self) -> dict:
        return asdict(self)


def git(repo_dir: str, *args: str, timeout: float = 120.0) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", repo_dir, *args],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise GitError(f"git {args[0]} timed out after {timeout:.0f} s") from e
    if out.returncode != 0:
        raise GitError(out.stderr.decode("utf-8", "replace").strip()[:500])
    return out.stdout.decode("utf-8", "replace")


def _parse(out: str) -> list[Commit]:
    commits = []
    for rec in out.split(_RS):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split(_FS)
        if len(parts) != 7:
            continue
        sha, an, ae, ad, cd, s, b = parts
        # `git log -L` prints the diff after the record; -s suppresses it, but strip any stray lines.
        commits.append(Commit(sha.strip(), an, ae, ad, cd, s, b.strip()))
    return commits


def show(repo_dir: str, ref: str) -> Commit:
    commits = _parse(git(repo_dir, "show", "-s", f"--format={_FORMAT}", ref))
    if not commits:
        raise GitError(f"no commit {ref}")
    return commits[0]


def line_at(repo_dir: str, ref: str, path: str, line: int) -> str:
    """The text of one line (1-based) of a file at a ref."""
    lines = git(repo_dir, "show", f"{ref}:{path}").splitlines()
    if not 1 <= line <= len(lines):
        raise GitError(f"{path} has {len(lines)} lines at {ref[:10]}; line {line} does not exist")
    return lines[line - 1]


def walk(repo_dir: str, ref: str, path: str, line: int, timeout: float = 120.0) -> list[Commit]:
    """Every commit that touched this line, newest first. The last one first wrote it.

    Unlike blame, this goes past reformatting and moves: `git log -L` follows the line's range back
    through each change to it.
    """
    out = git(
        repo_dir,
        "log",
        f"-L{line},{line}:{path}",
        "-s",
        f"--format={_FORMAT}",
        ref,
        timeout=timeout,
    )
    return _parse(out)


def blame(repo_dir: str, ref: str, path: str, line: int, timeout: float = 60.0) -> str:
    """The sha `git blame` shows for this line: what most engineers read first."""
    out = git(
        repo_dir, "blame", "--porcelain", f"-L{line},{line}", ref, "--", path, timeout=timeout
    )
    first = out.split("\n", 1)[0].split()
    if not first:
        raise GitError("blame returned nothing")
    return first[0]


_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_KEYWORDS = set(
    """and assert async await break case catch class const continue def default defined del do elif else
    elsif end ensure enum except export extends false final finally for from func function go if import in
    interface is lambda let module new nil none not null or package pass private protected public raise
    require rescue return self static struct super switch then this throw true try type unless until var
    void when while with yield string int bool err error""".split()
)


def main_identifier(text: str) -> str | None:
    """The longest identifier on a line, which is what someone would paste into `git log -S`."""
    idents = [t for t in _IDENT.findall(text) if t.lower() not in _KEYWORDS]
    return max(idents, key=len) if idents else None


def log_s(
    repo_dir: str, ref: str, path: str, needle: str, limit: int = 5, timeout: float = 120.0
) -> list[Commit]:
    """The oldest `limit` commits on this path that added or removed `needle` (git's pickaxe)."""
    out = git(
        repo_dir,
        "log",
        f"-S{needle}",
        "--reverse",
        f"--format={_FORMAT}",
        ref,
        "--",
        path,
        timeout=timeout,
    )
    return _parse(out)[:limit]


def last_seen(repo_dir: str, ref: str, email: str) -> str | None:
    """When this author last committed anywhere in the repo, up to ref."""
    out = git(repo_dir, "log", "-1", "--format=%aI", f"--author=<{email}>", ref).strip()
    return out or None
