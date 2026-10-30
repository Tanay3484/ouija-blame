"""Which passages the medium gets to see: BM25 against the line's own words, plus a nudge for reasons.

A PR thread can hold hundreds of paragraphs and a 4B model reads about sixteen well, so ranking decides
what the séance can possibly find. Commit messages on the walk are always shown, because blame-style
evidence should never be worse than blame.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .sources import Passage

_TOKEN = re.compile(r"[A-Za-z][a-z]+|[A-Z]+(?![a-z])|\d+")
_REASON_CUES = set(
    """because otherwise needed need needs required requires require prevent prevents avoid avoids
    workaround hack compat compatibility backward break breaks broke broken regression bug fix fixes issue
    without ensure ensures so why since crash fails failing failure race deadlock leak""".split()
)


def tokens(text: str) -> list[str]:
    """Words, with camelCase and snake_case split, lower-cased."""
    return [t.lower() for t in _TOKEN.findall(text) if len(t) > 1]


def rank(
    passages: list[Passage],
    query: str,
    kinds: dict[str, str],
    limit: int = 16,
    always_kind: str = "commit",
    always_max: int = 6,
) -> list[Passage]:
    """Top passages for a query. `kinds` maps source id → kind; up to `always_max` commit passages are
    kept first, in walk order."""
    if not passages:
        return []
    docs = [tokens(p.text) for p in passages]
    n = len(docs)
    avg = sum(len(d) for d in docs) / n or 1.0
    df = Counter(t for d in docs for t in set(d))
    q = [t for t in tokens(query)]
    k1, b = 1.4, 0.75

    def score(i: int) -> float:
        tf = Counter(docs[i])
        s = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(docs[i]) / avg))
        cues = sum(1 for t in set(docs[i]) if t in _REASON_CUES)
        return s + 0.6 * min(cues, 3)

    always = [p for p in passages if kinds.get(p.source_id) == always_kind][:always_max]
    taken = {p.id for p in always}
    rest = sorted((i for i, p in enumerate(passages) if p.id not in taken), key=lambda i: -score(i))
    return always + [passages[i] for i in rest[: max(0, limit - len(always))]]
