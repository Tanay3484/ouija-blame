"""Write the answer card for every gallery séance into results/cards/<id>.json (Gemma via local Ollama).

    python -I scripts/add_cards.py

The card is written after the quotes were chosen and checked, from those quotes only, so it changes nothing
in results/seances or the evaluation. build_gallery.py merges the cards into the gallery.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ouija.config import get_settings  # noqa: E402
from ouija.explain import explain  # noqa: E402
from ouija.ollama import OllamaClient  # noqa: E402


def main() -> None:
    s = get_settings()
    llm = OllamaClient(s.ollama_base, s.model, timeout_s=s.llm_timeout_s, num_ctx=s.llm_num_ctx)
    out_dir = ROOT / "results" / "cards"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted((ROOT / "results" / "seances").glob("*.json")) + sorted(
        (ROOT / "results" / "extra_seances").glob("*.json")
    )
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        sid = d.get("extra_id") or d["case"]["id"]
        target = out_dir / f"{sid}.json"
        if target.exists():
            continue
        card = explain(llm, d["path"], d["line_text"], d["quotes"], d["silent"])
        target.write_text(json.dumps(card, indent=1, ensure_ascii=False), encoding="utf-8")
        print(sid, "cites", card["cites"], "error", card["error"], flush=True)


if __name__ == "__main__":
    main()
