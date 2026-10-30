"""PR and issue numbers written in commit messages and PR descriptions."""

from __future__ import annotations

import re

_PR_IN_MESSAGE = [
    re.compile(r"^Merge pull request #(\d+)", re.M),
    re.compile(r"\(#(\d+)\)\s*$", re.M),  # squash merges: "Fix the thing (#1234)"
]
_CLOSES = re.compile(r"\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\b:?\s+#(\d+)", re.I)


def prs_in_message(message: str) -> list[int]:
    found: list[int] = []
    for pat in _PR_IN_MESSAGE:
        for m in pat.finditer(message):
            n = int(m.group(1))
            if n not in found:
                found.append(n)
    return found


def linked_issues(text: str, owner: str, repo: str, limit: int = 3) -> list[int]:
    """Issues a PR says it fixes, closes or resolves, or links in full."""
    url = re.compile(rf"github\.com/{re.escape(owner)}/{re.escape(repo)}/issues/(\d+)", re.I)
    found: list[int] = []
    for pat in (_CLOSES, url):
        for m in pat.finditer(text or ""):
            n = int(m.group(1))
            if n not in found:
                found.append(n)
    return found[:limit]


_LINE_URL = re.compile(
    r"github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/blob/(?P<ref>[^/]+)/(?P<path>[^#?]+)#L(?P<line>\d+)"
)


def parse_line_url(url: str) -> dict | None:
    """`https://github.com/o/r/blob/<ref>/path/file.go#L42` → its parts, or None."""
    m = _LINE_URL.search(url.strip())
    if not m:
        return None
    d = m.groupdict()
    d["line"] = int(d["line"])
    d["repo"] = d["repo"].removesuffix(".git")
    return d
