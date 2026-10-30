"""The medium: Gemma reads the passages and points at the ones that give a reason. It never quotes.

The model returns passage ids from an enum, so it cannot write words into a ghost's mouth: the text shown
is always the source's own. Its single line of its own is shown apart, labelled as the medium's.
"""

from __future__ import annotations

from .ollama import ChatJSON, LLMError
from .sources import Passage, Source

SYSTEM = """You are the medium at a seance for one line of code. You never speak for the people who wrote it. You only point at what they wrote.

You get the line and numbered passages from its history: commit messages, pull request text, review comments and issues.

Choose up to 3 passages that say WHY this line exists: the problem it solves, what it protects against, or what breaks without it.
These are NOT reasons: saying what the code does, or that it was moved, renamed, reformatted, refactored, bumped or cleaned up.
If no passage gives a reason, set found to false and choose none. Saying nothing is better than a wrong reason.

Then write one short sentence as the medium (at most 25 words) that introduces what the passages say. Add no facts that are not in them."""

MEDIUM_MAX = 200


def schema(ids: list[str], max_chosen: int) -> dict:
    # Fields in the order we want them written; every string capped (Week 2: small models can loop).
    return {
        "type": "object",
        "properties": {
            "found": {"type": "boolean"},
            "passages": {
                "type": "array",
                "items": {"type": "string", "enum": ids},
                "maxItems": max_chosen,
            },
            "medium": {"type": "string", "maxLength": MEDIUM_MAX},
        },
        "required": ["found", "passages", "medium"],
    }


def prompt(path: str, line_text: str, shown: list[Passage], sources: dict[str, Source]) -> str:
    parts = [f"File: {path}", f"Line: {line_text.strip()}", "", "Passages:"]
    for i, p in enumerate(shown, 1):
        s = sources[p.source_id]
        where = s.kind.replace("_", " ")
        parts.append(f"[P{i}] ({where} by {s.author}, {s.created[:10]}) {p.text[:500]}")
    parts.append("")
    parts.append("Which passages, if any, say why this line exists?")
    return "\n".join(parts)


def consult(
    llm: ChatJSON,
    path: str,
    line_text: str,
    shown: list[Passage],
    sources: dict[str, Source],
    max_chosen: int = 3,
) -> dict:
    """Ask the medium. Returns {found, chosen: [Passage], medium, error}."""
    if not shown:
        return {"found": False, "chosen": [], "medium": "", "error": None}
    ids = [f"P{i}" for i in range(1, len(shown) + 1)]
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt(path, line_text, shown, sources)},
    ]
    try:
        out = llm.chat_json(messages, schema(ids, max_chosen), temperature=0.0)
    except LLMError as e:
        return {"found": False, "chosen": [], "medium": "", "error": str(e)}
    picked: list[Passage] = []
    for pid in out.get("passages") or []:
        if isinstance(pid, str) and pid in ids:
            p = shown[ids.index(pid)]
            if p not in picked:
                picked.append(p)
    found = bool(out.get("found")) and bool(picked)
    medium = str(out.get("medium") or "").strip().strip('"“”')[:MEDIUM_MAX]
    return {
        "found": found,
        "chosen": picked[:max_chosen] if found else [],
        "medium": medium,
        "error": None,
    }
