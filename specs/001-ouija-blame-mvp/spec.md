# 001 — Ouija Blame MVP: requirements, design and tasks

Status: Draft (built through overnight on 2026-10-30 with Tanay's agreement; Tanay reviews and sets Approved)
Owner: Tanay
Updated: 2026-10-30

The build started 13 hours before the deadline, so the three phases share one file. The brief is
`../000-brief/brief.md`.

## 1. Requirements

### R1 Summon (the séance)

- R1.1 WHEN a user gives a public GitHub repo, a file path and a line number (or a GitHub link to one
  line), the system SHALL walk that line's history back to the commit that first wrote it.
- R1.2 The system SHALL gather, for the commits on that walk: commit messages, the PR description, PR
  comments, review comments, and the body and comments of issues the PR links.
- R1.3 WHEN a commit on the walk carries an `Entire-Checkpoint` trailer and the repo publishes that
  checkpoint, the system SHALL also gather the prompts from that agent session.
- R1.4 The ghost SHALL be the author of the commit that first wrote the line, shown by GitHub handle or git
  name, with the date they were last seen in the walk. The ghost is a generic pixel ghost, never a photo.

### R2 Speak only in recorded words

- R2.1 Every line the ghost or another voice speaks SHALL be a verbatim passage from a gathered source,
  shown with its author and a link to the commit, PR, comment, issue or checkpoint.
- R2.2 The model SHALL only choose passages by id; it SHALL NOT write the quoted text.
- R2.3 IF a chosen passage is not found verbatim in its source, THEN the system SHALL drop it and count the
  drop.
- R2.4 Text the model writes (the medium's line) SHALL be shown in a different style and labelled as the
  medium's.
- R2.5 IF no passage explains the line, THEN the ghost SHALL say "I never wrote down why." and the system
  SHALL show what git blame shows.

### R3 Evidence (evaluation)

- R3.1 A miner SHALL find commits named `Revert "Remove…"`, `"Delete…"` or `"Drop…"` in local clones, pair
  each with the commit it reverts, and pick one deleted-then-restored line as the case.
- R3.2 Each method SHALL see only history from before the deletion commit: the walk starts at the
  deletion's parent, and comments created at or after the deletion are excluded.
- R3.3 The evaluation SHALL run four methods (B1 blame message, B2 blame plus its PR, B3 `git log -S` top 5,
  the séance) and write what each method shows to `results/`.
- R3.4 Grading SHALL be blind to method: evidence is shuffled under random ids before grading.
- R3.5 A script SHALL compute reason-found rates, reached-origin rates, honest-silence rate, words shown per
  method, and a paired bootstrap interval for séance minus B2, from `results/` files alone.

### R4 App and hosting

- R4.1 The web app SHALL work logged out, on a phone, and show a gallery of precomputed séances that needs
  no GitHub calls.
- R4.2 The server SHALL hold no GitHub token. GitHub API calls for live séances SHALL be made by the
  visitor's browser, optionally with the visitor's own token, which stays in that tab.
- R4.3 IF a live repo is larger than the size cap, THEN the system SHALL say so and point to the gallery.
- R4.4 The model routes SHALL be rate-limited per client.
- R4.5 The app and Gemma (Ollama) SHALL deploy to Render from one Blueprint.

### Non-goals

As in the brief, plus: no accounts, no stored séances on the server, no APK.

## 2. Design

### Package layout (`backend/ouija/`, Python 3.11, FastAPI)

| Module | Job |
|--------|-----|
| `config.py` | Settings, env prefix `OB_` |
| `gitwalk.py` | `walk(repo_dir, ref, path, line)` → commits touching the line, newest first (`git log -L`); `blame(...)`; `log_s(...)` |
| `sources.py` | Raw GitHub JSON plus commits → `Source` and `Passage` lists; drops bots, commands (`/lgtm`), and anything at or after the cutoff |
| `links.py` | PR numbers from commit messages (`(#123)`, `Merge pull request #123`); issue numbers a PR links (`Fixes #12`, full issue URLs) |
| `rank.py` | BM25 over passages, query from the line's identifiers and the file path; top 16 go to the model |
| `medium.py` | Gemma prompt and schema: `{found, passages: [ids ≤ 3], medium: ≤ 160 chars}`; ids are an enum |
| `verify.py` | The quote checker: whitespace-normalised verbatim match of each passage in its source text |
| `seance.py` | Orchestration: walk → sources → rank → medium → verify → `Seance` |
| `entire.py` | Reads `refs/entire/checkpoints/…` for a checkpoint id and pulls the user prompts |
| `github.py` | Cached REST client for the evaluation (local `gh` token); the server never uses a token |
| `api.py` | `/api/health`, `/api/walk`, `/api/seance`, `/api/gallery`, static files |
| `evaluation/` | `mine.py`, `methods.py`, `grade.py`, `stats.py` |

### Live flow (no server token)

1. Browser `POST /api/walk {repo, path, line}`. The server clones (`--filter=tree:0` is too slow for `git
   log -L`, so a full shallow-free clone under the size cap, cached on disk, oldest evicted) and returns the
   commits and the PR and issue numbers it can parse.
2. The browser fetches those PRs, comments, review comments and linked issues from `api.github.com`
   (visitor's own rate limit, optional own token), and `commits/{sha}/pulls` for commits with no number.
3. Browser `POST /api/seance {walk, github: {raw JSON}}`. The server builds sources, ranks, asks Gemma,
   verifies and returns the séance. The evaluation calls the same `seance.run()` with JSON from the cache.

### The medium's prompt

The model sees the line, the file path, and up to 16 numbered passages with author and kind. It is asked
which passages, if any, say *why the line exists or what breaks without it*, and to write one short line
introducing them. Fields are in the order `found`, `passages`, `medium`; every string has a `maxLength`;
`num_predict` is capped (Week 2 lessons).

### Risks

- `git log -L` on Kubernetes-sized files can take tens of seconds: precompute the gallery; cap live repos
  at 150 MB.
- Gemma 4B on Render CPU takes 30–90 s per séance: the crystal ball shows real progress while it waits.
- Real people: guardrails as in the brief; no photos; "left the project", never dead.

## 3. Tasks

All `@ai` this week except where marked. Commits cite task and requirement ids.

- [x] T1 Scaffold: package, settings, ruff, pytest, CI `tests` job (R4.5)
- [x] T2 `gitwalk` walk, blame, `log -S`, with tests on a temp repo built in the test (R1.1, R3.3)
- [x] T3 `links`, `sources`, cutoff and bot filters, with tests (R1.2, R3.2)
- [x] T4 `verify` quote checker and `rank`, with tests (R2.1, R2.3)
- [x] T5 `medium` prompt, schema and parsing with a fake model; `seance.run` (R2.2, R2.4, R2.5, R1.4)
- [x] T6 `entire` checkpoint reader (R1.3)
- [x] T7 Miner and cached GitHub client; mine about 50 cases (R3.1)
- [x] T8 Answer key: read each revert's PR, write the reason or drop the case (R3.1)
- [x] T9 Methods B1–B3 and the séance over all cases; blind grading file (R3.2–R3.4)
- [x] T10 Grading by Claude; `stats.py` and `results/summary.md` (R3.4, R3.5)
- [x] T11 API with rate limit, gallery built from the evaluation run (R4.1, R4.3, R4.4)
- [x] T12 App: pixel crystal ball, Ouija planchette, séance and gallery screens, browser-side GitHub calls (R4.1, R4.2, R2.4, R2.5)
- [x] T13 Dockerfile, Ollama service, `render.yaml`; deploy and test logged out on a phone (R4.5)
- [x] T14 README, licence, post draft in `drafts/` with TODO(Tanay) markers
- [ ] T15 `@human` Tanay re-grades 10 random cases blind; agreement goes in the post (R3.4)
- [ ] T16 `@human` Tanay's opening in his own words, first-user session, publishing

## Changelog

- 2026-10-30: First draft; requirements, design and tasks in one file because of the deadline.
- 2026-10-31: Built. Changes from the draft: the PR focus is the 4 newest commits plus the origin (not 8),
  to fit a visitor's 60 unauthenticated GitHub calls an hour; the evaluation's GitHub client calls the `gh`
  CLI so the token never passes through our code; grading has two levels (R the revert's reason, E another
  written reason, N none) after the first séances showed the reason a line was written and the reason it
  must stay usually differ; evidence over 400 words is graded from an excerpt (stated in the post).
  Known gap: `git log -L` does not follow a line across file moves.
