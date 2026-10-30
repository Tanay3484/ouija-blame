"""Mine the dataset: code someone deleted, it broke, and a revert put it back.

For each commit named `Revert "Remove…"` (or Delete, Drop), find the commit it reverts (the deletion D),
and pick one line D removed that the revert restored. The case is that line as it stood at D's parent,
with D's commit time as the cutoff: a method may only see what existed before the deletion.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from ..gitwalk import Commit, GitError, _parse, git, line_at, show

_REVERT_GREP = r'^Revert "(Remove|Removed|Delete|Deleted|Drop|Dropped|Rm) '
_REVERTS_SHA = re.compile(r"reverts commit ([0-9a-f]{7,40})", re.I)
_QUOTED = re.compile(r'^Revert "(.*)"(?:\s*\(#\d+\))?\s*$')
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

CODE_EXT = (
    ".rb", ".py", ".go", ".js", ".ts", ".java", ".c", ".h", ".cc", ".cpp", ".rs", ".sh", ".yml",
    ".yaml", ".rake", ".erb",
)  # fmt: skip
_SKIP_PATH = re.compile(
    r"(^|/)(tests?|spec|testdata|test_data|e2e|vendor|third_party|docs?|changelogs?|fixtures?)/"
    r"|_test\.go$|(^|/)test_[^/]*\.py$|_spec\.rb$|_test\.rb$|zz_generated|\.pb\.go$|generated",
    re.I,
)
_COMMENT = re.compile(r"^\s*(#|//|/\*|\*|--)")


@dataclass
class Case:
    id: str
    repo: str  # owner/name
    revert: str
    revert_subject: str
    deletion: str
    deletion_subject: str
    parent: str
    cutoff: str  # deletion's commit time, ISO 8601
    path: str
    line: int
    line_text: str

    def to_dict(self) -> dict:
        return asdict(self)


def is_candidate_path(path: str) -> bool:
    return path.endswith(CODE_EXT) and not _SKIP_PATH.search(path)


def is_candidate_line(text: str) -> bool:
    s = text.strip()
    return len(s) >= 12 and bool(re.search(r"[A-Za-z]", s)) and not _COMMENT.match(s)


def parse_diff(diff: str) -> dict[str, dict[str, list[tuple[int, str]]]]:
    """`git diff -U0` → {old_path: {"removed": [(old_line, text)], "added": [(new_line, text)]}}.

    Paths are the pre-image path; a file the diff adds (pre-image /dev/null) is keyed by its new path.
    """
    files: dict[str, dict[str, list[tuple[int, str]]]] = {}
    cur = None
    old_no = new_no = 0
    old_path = new_path = None
    for ln in diff.splitlines():
        if ln.startswith("diff --git"):
            cur, old_path, new_path = None, None, None
            continue
        if ln.startswith("--- "):
            old_path = ln[4:].removeprefix("a/") if ln[4:] != "/dev/null" else None
            continue
        if ln.startswith("+++ "):
            new_path = ln[4:].removeprefix("b/") if ln[4:] != "/dev/null" else None
            key = old_path or new_path
            cur = files.setdefault(key, {"removed": [], "added": []}) if key else None
            continue
        m = _HUNK.match(ln)
        if m:
            old_no, new_no = int(m.group(1)), int(m.group(3))
            continue
        if cur is None:
            continue
        if ln.startswith("-"):
            cur["removed"].append((old_no, ln[1:]))
            old_no += 1
        elif ln.startswith("+"):
            cur["added"].append((new_no, ln[1:]))
            new_no += 1
    return files


def reverted_commit(repo_dir: str, r: Commit) -> str | None:
    """The sha a revert undoes: from "This reverts commit X", else by the quoted subject."""
    m = _REVERTS_SHA.search(r.body)
    if m:
        try:
            return show(repo_dir, m.group(1)).sha
        except GitError:
            pass
    q = _QUOTED.match(r.subject)
    if not q:
        return None
    inner = q.group(1)
    out = git(
        repo_dir,
        "log",
        "-n",
        "40",
        "--format=%H\x1f%s",
        "--fixed-strings",
        f"--grep={inner}",
        f"{r.sha}^",
    )
    for row in out.splitlines():
        sha, _, subj = row.partition("\x1f")
        if subj.strip() == inner or re.sub(r"\s*\(#\d+\)$", "", subj.strip()) == inner:
            return sha
    return None


def mine_repo(repo_dir: str, owner_repo: str, limit: int = 60) -> tuple[list[Case], dict]:
    fmt = "\x1f".join(["%H", "%an", "%ae", "%aI", "%cI", "%s", "%b"]) + "\x1e"
    out = git(repo_dir, "log", "-E", "-i", f"--grep={_REVERT_GREP}", f"--format={fmt}", "HEAD")
    reverts = [
        c
        for c in _parse(out)
        if c.subject.startswith('Revert "') and 'Revert "Revert' not in c.subject
    ]
    stats = {"reverts": len(reverts), "no_deletion": 0, "no_line": 0, "dup": 0, "kept": 0}
    cases: list[Case] = []
    seen: set[str] = set()
    for r in reverts:
        if len(cases) >= limit:
            break
        try:
            d_sha = reverted_commit(repo_dir, r)
        except GitError:
            d_sha = None
        if not d_sha:
            stats["no_deletion"] += 1
            continue
        if d_sha in seen:
            stats["dup"] += 1
            continue
        seen.add(d_sha)
        try:
            d = show(repo_dir, d_sha)
            parent = git(repo_dir, "rev-parse", f"{d_sha}^1").strip()
            d_diff = parse_diff(git(repo_dir, "diff", "-U0", "--no-renames", parent, d_sha))
            r_diff = parse_diff(git(repo_dir, "diff", "-U0", "--no-renames", f"{r.sha}^1", r.sha))
        except GitError:
            stats["no_deletion"] += 1
            continue
        case = _pick_line(repo_dir, owner_repo, r, d, parent, d_diff, r_diff)
        if case is None:
            stats["no_line"] += 1
            continue
        cases.append(case)
    stats["kept"] = len(cases)
    return cases, stats


def _pick_line(repo_dir, owner_repo, r, d, parent, d_diff, r_diff) -> Case | None:
    for path, ch in d_diff.items():
        if not is_candidate_path(path) or path not in r_diff:
            continue
        restored = {t.strip() for _, t in r_diff[path]["added"]}
        for line_no, text in ch["removed"]:
            if not is_candidate_line(text) or text.strip() not in restored:
                continue
            try:
                if line_at(repo_dir, parent, path, line_no).strip() != text.strip():
                    continue
            except GitError:
                continue
            name = owner_repo.split("/")[1]
            return Case(
                id=f"{name}-{d.sha[:8]}",
                repo=owner_repo,
                revert=r.sha,
                revert_subject=r.subject,
                deletion=d.sha,
                deletion_subject=d.subject,
                parent=parent,
                cutoff=d.committed,
                path=path,
                line=line_no,
                line_text=text,
            )
    return None
