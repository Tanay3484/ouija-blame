# Ouija Blame

**Ask a line of code why it exists. The ghost of whoever wrote it answers, only in words they actually
wrote.**

Live: <https://ouija-blame.onrender.com> · DEV Hacktoberfest 2026, Week 4: Ghost in the Machine

Every codebase has a line nobody dares delete, and the person who knew why it is there has left. `git
blame` shows the last commit that touched the line, which is often a reformat. Ouija Blame walks the
line back to the commit that first wrote it, gathers what its author and reviewers wrote (commit
messages, the pull request, review comments, linked issues, and agent-session prompts recorded with
Entire), and lets an open-weight model, Gemma, point at the passages that say why. The model can only
choose passage numbers, never write the quote, and code checks every quote word for word against its
source. If nothing says why, the ghost says **"I never wrote down why."**

## Does it work? The evidence

The test set is code that someone deleted because it looked pointless, it broke, and a revert put it
back. Each revert is a real "why does this exist?" with the answer written down. Every method sees only
history from before the deletion; the revert is the answer key.

Results, method and limits: [`results/summary.md`](results/summary.md). Everything there is produced by
the scripts below from files in `results/`.

| Step | Command | Output |
|------|---------|--------|
| Mine reverted deletions from local clones | `python -I scripts/mine_reverts.py rails/rails=data/raw/rails.git …` | `results/cases.jsonl` |
| Gather each revert's own explanation for labelling | `python -I scripts/answer_pack.py` | `data/cache/answer_pack.md` (read by hand into `results/answer_key.json`) |
| Run the four methods | `python -I scripts/run_eval.py` | `results/runs/*.jsonl`, `results/seances/*.json`, `results/grading/blind.jsonl` |
| Grade blind | `python -I scripts/grading_sheet.py` | `results/grading/grades.json` |
| Numbers | `python -I scripts/stats.py` | `results/summary.md` |

Methods compared: the `git blame` commit message; blame plus its pull request; the five oldest `git log
-S` hits for the line's main identifier; the séance.

## How it works

```
line ──git log -L──▶ every commit that touched it ──▶ PRs, reviews, linked issues, Entire prompts
                                                              │
                     passages (verbatim slices) ◀─────────────┘
                              │ BM25 against the line's own words, top 16
                              ▼
                     Gemma 4B (Ollama): "which passages say why?" → ids only (enum)
                              │
                     quote checker: verbatim in source, or dropped
                              ▼
                     the ghost speaks, or "I never wrote down why."
```

- `backend/ouija/gitwalk.py`: `git log -L`, `git blame`, `git log -S` on a local clone.
- `backend/ouija/sources.py`: GitHub JSON → sources → passages that are always contiguous slices of the
  raw text; bots, `/lgtm` commands, PR templates and anything after the cutoff are dropped.
- `backend/ouija/medium.py`: the prompt and the JSON schema; passage ids are an enum.
- `backend/ouija/verify.py`: the quote checker.
- `backend/ouija/entire.py`: reads `refs/entire/checkpoints/…` with plain git.
- `backend/ouija/api.py`: live séances in three calls, so **the server holds no GitHub token**: the
  server clones and walks; the visitor's browser fetches PRs and comments from `api.github.com`
  (optionally with the visitor's own token, kept in the tab); the server asks the medium.
- `app/`: the pixel-art séance (TypeScript, Vite). All art is drawn in code.

## Run it

```sh
ollama pull gemma3:4b
python -m venv .venv && .venv/Scripts/pip install -e "backend[dev]"   # bin/ on macOS and Linux
cd app && npm ci && npm run build && cd ..
OB_STATIC_DIR=app/dist OB_GALLERY_DIR=app/public/gallery \
  .venv/Scripts/python -m uvicorn --app-dir backend --factory ouija.api:app_factory --port 8000
pytest backend                                                        # no network, fake model
```

Deploy: `render.yaml` (web service plus a private Ollama service with Gemma baked in).

## Ground rules

These are real people, so: public words only, always linked; the model's own words are shown apart and
labelled; the people here left projects or moved on, nobody is framed as dead; the ghost is a generic
sprite, never a photo. Ask in an issue to be removed from the gallery.

## Built with

Gemma 3 4B (open weights) through Ollama, FastAPI, Vite, Render. Built during the challenge window (from
2026-10-27) by Tanay with Claude Code; specs in [`specs/`](specs/). MIT licence.
