"""What the author left behind, as sources and passages.

A source is one written thing with an author, a date and a link: a commit message, a PR description, a
comment, a review comment, an issue, an agent-session prompt. A passage is a paragraph of a source, cut so
that it is always a contiguous run of the source's raw text. That is what lets the quote checker demand
verbatim matches.

The input is the raw JSON GitHub's REST API returns, keyed by path, so the evaluation (from a disk cache)
and the live app (from the visitor's browser) share this code.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .gitwalk import Commit
from .links import linked_issues, prs_in_message

_BOT_LOGIN = re.compile(
    r"(\[bot\]$|-bot$|-robot$|^fejta-bot$|^ansibot$|^istio-testing$|^rails-bot$)", re.I
)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_COMMAND_LINE = re.compile(
    r"^\s*/[a-z][\w-]*(\s|$)", re.I
)  # Prow commands: /lgtm, /kind bug, /assign
_TRAILER = re.compile(
    r"^\s*[A-Z][\w-]+(-by|-Id|-Checkpoint):\s", re.I
)  # Signed-off-by:, Change-Id:


@dataclass
class Source:
    id: str
    kind: str  # commit | pr | pr_comment | review_comment | review | issue | issue_comment | checkpoint
    url: str
    author: str
    created: str  # ISO 8601
    raw: str
    title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Passage:
    id: str
    source_id: str
    text: str
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def is_bot(user: dict | None) -> bool:
    if not user:
        return True
    return user.get("type") == "Bot" or bool(_BOT_LOGIN.search(user.get("login", "")))


def commit_sources(commits: list[Commit], owner: str, repo: str) -> list[Source]:
    return [
        Source(
            id=f"commit:{c.sha[:12]}",
            kind="commit",
            url=f"https://github.com/{owner}/{repo}/commit/{c.sha}",
            author=c.author,
            created=c.authored,
            raw=c.message,
            title=c.subject,
        )
        for c in commits
    ]


def pr_numbers(commits: list[Commit], github: dict, owner: str, repo: str) -> dict[str, list[int]]:
    """For each commit: PR numbers from its message, else from `commits/{sha}/pulls` if fetched."""
    out: dict[str, list[int]] = {}
    for c in commits:
        nums = prs_in_message(c.message)
        if not nums:
            pulls = github.get(f"repos/{owner}/{repo}/commits/{c.sha}/pulls") or []
            nums = [p["number"] for p in pulls if p.get("merged_at") or p.get("state")]
        out[c.sha] = nums[:1]
    return out


def github_sources(
    pr_nums: list[int], github: dict, owner: str, repo: str, cutoff: datetime | None
) -> list[Source]:
    """PR descriptions, comments, review comments, reviews, and the issues those PRs link."""
    out: list[Source] = []
    base = f"repos/{owner}/{repo}"

    def keep(created: str | None, user: dict | None, body: str | None) -> bool:
        if not body or not body.strip() or is_bot(user):
            return False
        return not (cutoff and created and parse_time(created) >= cutoff)

    issue_nums: list[int] = []
    for n in pr_nums:
        pr = github.get(f"{base}/pulls/{n}")
        if not pr:
            continue
        if keep(pr.get("created_at"), pr.get("user"), pr.get("body")):
            out.append(_gh_source(f"pr:{n}", "pr", pr, title=pr.get("title", "")))
        for c in github.get(f"{base}/issues/{n}/comments") or []:
            if keep(c.get("created_at"), c.get("user"), c.get("body")):
                out.append(_gh_source(f"pr_comment:{c['id']}", "pr_comment", c, title=f"PR #{n}"))
        for c in github.get(f"{base}/pulls/{n}/comments") or []:
            if keep(c.get("created_at"), c.get("user"), c.get("body")):
                title = f"PR #{n} review on {c.get('path', '')}"
                out.append(
                    _gh_source(f"review_comment:{c['id']}", "review_comment", c, title=title)
                )
        for r in github.get(f"{base}/pulls/{n}/reviews") or []:
            if keep(r.get("submitted_at"), r.get("user"), r.get("body")):
                r = {**r, "created_at": r.get("submitted_at")}
                out.append(_gh_source(f"review:{r['id']}", "review", r, title=f"PR #{n} review"))
        for i in linked_issues(pr.get("body") or "", owner, repo):
            if i not in issue_nums and i not in pr_nums:
                issue_nums.append(i)

    for n in issue_nums:
        issue = github.get(f"{base}/issues/{n}")
        if not issue:
            continue
        if keep(issue.get("created_at"), issue.get("user"), issue.get("body")):
            out.append(_gh_source(f"issue:{n}", "issue", issue, title=issue.get("title", "")))
        for c in github.get(f"{base}/issues/{n}/comments") or []:
            if keep(c.get("created_at"), c.get("user"), c.get("body")):
                out.append(
                    _gh_source(f"issue_comment:{c['id']}", "issue_comment", c, title=f"#{n}")
                )
    return out


def _gh_source(sid: str, kind: str, obj: dict, title: str = "") -> Source:
    return Source(
        id=sid,
        kind=kind,
        url=obj.get("html_url", ""),
        author=(obj.get("user") or {}).get("login", "?"),
        created=obj.get("created_at") or "",
        raw=obj.get("body") or "",
        title=title,
    )


def wanted_paths(commits: list[Commit], owner: str, repo: str) -> list[str]:
    """The API paths a séance would like for these commits before PR numbers are known (live flow)."""
    paths = []
    for c in commits:
        if not prs_in_message(c.message):
            paths.append(f"repos/{owner}/{repo}/commits/{c.sha}/pulls")
    return paths


def pr_paths(n: int, owner: str, repo: str) -> list[str]:
    base = f"repos/{owner}/{repo}"
    return [
        f"{base}/pulls/{n}",
        f"{base}/issues/{n}/comments",
        f"{base}/pulls/{n}/comments",
        f"{base}/pulls/{n}/reviews",
    ]


def issue_paths(n: int, owner: str, repo: str) -> list[str]:
    base = f"repos/{owner}/{repo}"
    return [f"{base}/issues/{n}", f"{base}/issues/{n}/comments"]


_MIN_PASSAGE = 25
_MAX_PASSAGE = 600


def passages(src: Source) -> list[Passage]:
    """Cut a source into paragraphs. Each passage is a contiguous slice of `src.raw`.

    HTML comments (PR templates) and bot commands (`/lgtm`) end a passage and are never part of one, and
    a paragraph longer than the cap is cut at sentence ends.
    """
    raw = src.raw.replace("\r\n", "\n")
    # Mask the parts that may not appear in a passage, keeping offsets, so slices stay verbatim.
    masked = _HTML_COMMENT.sub(lambda m: "\0" * len(m.group(0)), raw)
    lines = masked.split("\n")
    pieces: list[str] = []
    buf: list[str] = []
    for ln in lines:
        heading = ln.lstrip().startswith("#")
        if not ln.strip() or "\0" in ln or _COMMAND_LINE.match(ln) or heading:
            if buf:
                pieces.append("\n".join(buf))
                buf = []
            if heading and "\0" not in ln:
                pieces.append(ln.strip())  # kept only if long enough to say something
            continue
        buf.append(ln)
    if buf:
        pieces.append("\n".join(buf))

    out: list[Passage] = []
    min_len = (
        8 if src.kind == "commit" else _MIN_PASSAGE
    )  # "Fix typo" is still a commit's whole say
    for piece in pieces:
        for chunk in _split_long(piece.strip()):
            if len(chunk) < min_len or chunk.startswith("#") and len(chunk) < 60:
                continue
            if all(_TRAILER.match(ln) for ln in chunk.splitlines()):
                continue
            if chunk not in raw:  # paranoia: only verbatim slices survive
                continue
            out.append(Passage(id=f"{src.id}#{len(out)}", source_id=src.id, text=chunk))
    return out


def _split_long(text: str) -> list[str]:
    if len(text) <= _MAX_PASSAGE:
        return [text]
    chunks, start = [], 0
    for m in re.finditer(r"[.!?](\s+)", text):
        if m.end() - start >= _MAX_PASSAGE // 2:
            chunks.append(text[start : m.start() + 1])
            start = m.end()
    chunks.append(text[start:])
    return [c for c in chunks if c.strip()]
