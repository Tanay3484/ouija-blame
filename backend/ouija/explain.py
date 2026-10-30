"""The answer card: what the line does, why it exists, and what to check before changing it.

This runs after the medium has chosen passages and the quote checker has passed them, so it never changes
what the séance found (or the evaluation). Gemma writes it in its own words and it is labelled as such.
The "why" may only restate the quotes: each claim cites a quote number, and code drops the "why" if it
cites nothing that exists. "What" is read from the code line itself, which needs no quote.
"""

from __future__ import annotations

import re

from .ollama import ChatJSON, LLMError

NOT_WRITTEN = (
    "Nobody wrote down why this line exists, at least not anywhere the séance could reach."
)
UNCITED = "The quotes below are the closest the history comes; they do not state a reason outright."

SYSTEM = """You explain one line of code to a developer who is about to change or delete it.
You get the line, its file, and numbered quotes from the people who wrote and reviewed it.

Write three short fields:
- what: one sentence on what the line does, judged from the code itself.
- why: one to three sentences, in your own words, on the problem or need the quotes describe: the reason the line exists. Do not copy the quotes. After each claim put the quote number in brackets, like [1] or [2]. If the quotes only say what changed and never why, write exactly: The history does not say why.
- next: one sentence on what to check before changing or deleting it, based on the quotes.

Plain words. Nothing in "why" that the quotes do not support."""

SCHEMA = {
    "type": "object",
    "properties": {
        "what": {"type": "string", "maxLength": 220},
        "why": {"type": "string", "maxLength": 480},
        "next": {"type": "string", "maxLength": 240},
    },
    "required": ["what", "why", "next"],
}

_CITE = re.compile(r"\[(\d+)\]")
_MULTI = re.compile(r"\[(\d+(?:\s*,\s*\d+)+)\]")
_SILENT = "The history does not say why."


def prompt(path: str, line_text: str, quotes: list[dict]) -> str:
    parts = [f"File: {path}", f"Line: {line_text.strip()}", "", "Quotes:"]
    for i, q in enumerate(quotes, 1):
        parts.append(
            f"[{i}] ({q['kind'].replace('_', ' ')} by {q['author']}, {q['created'][:10]}) {q['text'][:700]}"
        )
    return "\n".join(parts)


def clean(text: str) -> str:
    """One line, no curly quote marks (the model decorates with them, often unbalanced)."""
    text = " ".join(str(text or "").split()).replace("“", "").replace("”", "")
    text = _MULTI.sub(lambda m: "".join(f"[{n.strip()}]" for n in m.group(1).split(",")), text)
    return text.strip().strip('"')


def explain(llm: ChatJSON, path: str, line_text: str, quotes: list[dict], silent: bool) -> dict:
    """{what, why, next, cites, error}. Never raises: a dead model leaves the card without prose."""
    if silent or not quotes:
        quotes = []
    try:
        out = llm.chat_json(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt(path, line_text, quotes)},
            ],
            SCHEMA,
            temperature=0.2,
            num_predict=300,
        )
    except LLMError as e:
        return {
            "what": "",
            "why": NOT_WRITTEN if silent else "",
            "next": "",
            "cites": [],
            "error": str(e),
        }
    what, why, nxt = clean(out.get("what")), clean(out.get("why")), clean(out.get("next"))
    cites = sorted({int(n) for n in _CITE.findall(why) if 1 <= int(n) <= len(quotes)})
    # Citations to quotes that do not exist are removed; a "why" with none left is not shown.
    why = _CITE.sub(
        lambda m: m.group(0) if 1 <= int(m.group(1)) <= len(quotes) else "", why
    ).strip()
    if cites and _SILENT in why:
        why = why.replace(
            _SILENT, ""
        ).strip()  # a cited reason and "it does not say why" cannot both stand
    if silent or not quotes:
        why = NOT_WRITTEN
    elif not cites:
        why = UNCITED
    return {"what": what, "why": why, "next": nxt, "cites": cites, "error": None}
