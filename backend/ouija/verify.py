"""The quote checker: a ghost may only say what is written, word for word, in a cited source."""

from __future__ import annotations

import re

_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Collapse runs of whitespace, so a re-wrapped line still counts as the same words."""
    return _WS.sub(" ", text.replace("\r\n", "\n")).strip()


def is_verbatim(quote: str, source_text: str) -> bool:
    q = normalise(quote)
    return bool(q) and q in normalise(source_text)
