"""Numbers for the post, from the runs and the blind grades alone.

Grades per evidence item: "R" gives the reason the revert gave, "E" gives a recorded reason the line
exists that is not the revert's, "N" gives no reason. The key maps each blind id back to its method.
"""

from __future__ import annotations

import random
import statistics
from collections import defaultdict

METHODS = ["b1", "b2", "b3", "seance"]
NAMES = {
    "b1": "git blame message",
    "b2": "blame + its PR",
    "b3": "git log -S, 5 oldest",
    "seance": "séance",
}


def paired_bootstrap(
    a: list[int], b: list[int], n: int = 10_000, seed: int = 20261031
) -> tuple[float, float, float]:
    """Mean of a − b and a 95% interval, resampling cases (pairs) with replacement."""
    assert len(a) == len(b) and a
    rng = random.Random(seed)
    k = len(a)
    diffs = [x - y for x, y in zip(a, b, strict=True)]
    means = []
    for _ in range(n):
        s = sum(diffs[rng.randrange(k)] for _ in range(k))
        means.append(s / k)
    means.sort()
    return sum(diffs) / k, means[int(0.025 * n)], means[int(0.975 * n) - 1]


def summarise(
    runs: dict[str, list[dict]], blind: list[dict], key: dict[str, str], grades: dict[str, str]
) -> dict:
    by = defaultdict(dict)  # case -> method -> grade
    for item in blind:
        g = grades.get(item["gid"])
        if g is None:
            raise ValueError(f"{item['gid']} is not graded")
        by[item["case"]][key[item["gid"]]] = g
    cases = sorted(by)
    out: dict = {"cases": len(cases), "methods": {}}
    for m in METHODS:
        rows = {r["case"]: r for r in runs[m]}
        r_hits = [int(by[c].get(m) == "R") for c in cases]
        e_hits = [int(by[c].get(m) in ("R", "E")) for c in cases]
        words = [rows[c]["words"] for c in cases if c in rows]
        out["methods"][m] = {
            "name": NAMES[m],
            "reason_match": sum(r_hits),
            "explains": sum(e_hits),
            "median_words": statistics.median(words) if words else 0,
            "mean_words": round(statistics.mean(words), 1) if words else 0,
            "errors": sum(1 for c in cases if rows.get(c, {}).get("error")),
        }

    # Blame against the walk: how often the commit blame shows is the one that first wrote the line.
    sea = {r["case"]: r for r in runs["seance"]}
    b1 = {r["case"]: r for r in runs["b1"]}
    b3 = {r["case"]: r for r in runs["b3"]}
    with_walk = [c for c in cases if sea.get(c, {}).get("origin") and b1.get(c, {}).get("commits")]
    out["blame_is_origin"] = sum(1 for c in with_walk if b1[c]["commits"][0] == sea[c]["origin"])
    out["log_s_has_origin"] = sum(
        1 for c in with_walk if sea[c]["origin"] in b3.get(c, {}).get("commits", [])
    )
    out["walk_cases"] = len(with_walk)
    out["median_walk_length"] = (
        statistics.median(len(sea[c]["walk"]) for c in with_walk) if with_walk else 0
    )

    # Honest silence. A case is answerable if any method's evidence gave a reason (pooled judgement).
    answerable = [c for c in cases if any(g in ("R", "E") for g in by[c].values())]
    unanswerable = [c for c in cases if c not in answerable]
    silent = {c for c in cases if sea.get(c, {}).get("silent")}
    out["answerable"] = len(answerable)
    out["seance_silent"] = len(silent)
    out["silent_when_unanswerable"] = len([c for c in unanswerable if c in silent])
    out["silent_when_answerable"] = len([c for c in answerable if c in silent])
    out["spoke_without_reason"] = len(
        [c for c in cases if c not in silent and by[c].get("seance") == "N"]
    )

    for metric in ("R", "RE"):
        ok = {"R": ("R",), "RE": ("R", "E")}[metric]
        s = [int(by[c].get("seance") in ok) for c in cases]
        for base in ("b1", "b2", "b3"):
            b = [int(by[c].get(base) in ok) for c in cases]
            mean, lo, hi = paired_bootstrap(s, b)
            out[f"seance_minus_{base}_{metric}"] = {
                "diff": round(mean, 3),
                "lo": round(lo, 3),
                "hi": round(hi, 3),
            }
    out["per_case"] = {c: by[c] for c in cases}
    return out


def markdown(s: dict) -> str:
    n = s["cases"]
    pct = lambda k: f"{k}/{n} ({100 * k / n:.0f}%)"  # noqa: E731
    lines = [
        "# Results",
        "",
        f"{n} deleted-then-restored lines from Rails, Kubernetes, Home Assistant, Ansible and Istio. Every method",
        "saw only history from before the deletion. Grades were given blind to method.",
        "",
        "| Method | Gives the revert's reason | Gives a recorded reason (any) | Median words to read |",
        "|--------|---------------------------|-------------------------------|----------------------|",
    ]
    for m in METHODS:
        r = s["methods"][m]
        lines.append(
            f"| {r['name']} | {pct(r['reason_match'])} | {pct(r['explains'])} | {r['median_words']:.0f} |"
        )
    lines += [
        "",
        "Séance minus baseline, paired bootstrap (10,000 resamples of cases), 95% interval:",
        "",
    ]
    for base in ("b1", "b2", "b3"):
        for metric, label in (("R", "revert's reason"), ("RE", "any recorded reason")):
            d = s[f"seance_minus_{base}_{metric}"]
            lines.append(
                f"- vs {s['methods'][base]['name']}, {label}: {d['diff']:+.2f} ({d['lo']:+.2f} to {d['hi']:+.2f})"
            )
    w = s["walk_cases"]
    lines += [
        "",
        f"- `git blame` showed the commit that first wrote the line in {s['blame_is_origin']}/{w} cases; the walk always reaches it (median {s['median_walk_length']:.0f} commits per line).",
        f"- `git log -S` (5 oldest) included that commit in {s['log_s_has_origin']}/{w} cases.",
        f"- Answerable cases (some method surfaced a reason): {s['answerable']}/{n}.",
        f"- The séance stayed silent in {s['seance_silent']}/{n}: {s['silent_when_unanswerable']} of {n - s['answerable']} unanswerable cases, and {s['silent_when_answerable']} answerable ones it missed.",
        f"- It spoke without giving a reason in {s['spoke_without_reason']} cases.",
    ]
    return "\n".join(lines) + "\n"
