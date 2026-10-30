"""Gather each revert's own explanation (its message, its PR, the issues that PR links) for labelling.

Writes data/cache/answer_pack.md, which a person reads to write results/answer_key.json. This is the
answer key's raw material and is never shown to any method.

    python -I scripts/answer_pack.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ouija.github import CachedGitHub  # noqa: E402
from ouija.links import linked_issues, prs_in_message  # noqa: E402
from ouija.sources import is_bot  # noqa: E402

LIMIT = 900


def clip(text: str, n: int = LIMIT) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n] + " […]"


def main() -> None:
    gh = CachedGitHub(str(ROOT / "data" / "cache" / "github"))
    cases = [
        json.loads(ln)
        for ln in (ROOT / "results" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    out = []
    for c in cases:
        owner, repo = c["repo"].split("/")
        base = f"repos/{owner}/{repo}"
        rc = gh.get(f"{base}/commits/{c['revert']}") or {}
        msg = (rc.get("commit") or {}).get("message", c["revert_subject"])
        nums = prs_in_message(msg)
        if not nums:
            nums = [p["number"] for p in gh.get(f"{base}/commits/{c['revert']}/pulls") or []][:1]
        out.append(f"## {c['id']}\n")
        out.append(f"- line: `{c['line_text'].strip()[:160]}` in `{c['path']}`")
        out.append(f"- deletion: {c['deletion_subject']}")
        out.append(f"- revert message: {clip(msg, 600)}\n")
        for n in nums[:1]:
            pr = gh.get(f"{base}/pulls/{n}") or {}
            out.append(
                f"### Revert PR #{n}: {pr.get('title', '')}\n\n{clip(pr.get('body') or '')}\n"
            )
            comments = [
                x for x in gh.get(f"{base}/issues/{n}/comments") or [] if not is_bot(x.get("user"))
            ]
            for x in comments[:6]:
                out.append(f"- **{x['user']['login']}**: {clip(x.get('body'), 500)}")
            for i in linked_issues(pr.get("body") or "", owner, repo)[:2]:
                iss = gh.get(f"{base}/issues/{i}") or {}
                out.append(
                    f"\n### Linked #{i}: {iss.get('title', '')}\n\n{clip(iss.get('body') or '', 600)}"
                )
        out.append("\n---\n")
    p = ROOT / "data" / "cache" / "answer_pack.md"
    p.write_text("\n".join(out), encoding="utf-8")
    print(f"{len(cases)} cases, {gh.calls} API calls, wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
