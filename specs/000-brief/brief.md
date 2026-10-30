# Brief — Ouija Blame

Status: Draft (Tanay agreed in chat on 2026-10-30 to build through with the cuts below; Tanay sets Approved on review)
Owner: Tanay
Updated: 2026-10-30

## Product

**Ouija Blame** is a pixel-art séance game for the question that haunts every legacy codebase: **why does this line exist?**

1. You paste a public GitHub repo (or a link to one line), pick a file, and tap the cursed line.
2. A crystal ball lights up and the séance starts. Behind it, code walks the line's whole history, not just
   the last commit that touched it: past renames, reformats and moves, back to the commit that wrote it.
   Code then gathers what the author left behind: commit messages, the PR description, review threads,
   linked issues and, when the commit has one, the Entire agent session behind it (the prompt the author
   typed is often the only place the "why" was ever written).
3. **The ghost** of the person who wrote it appears ("last seen in this repo: March 2021") and answers
   **only in their own recorded words**. Each line the ghost speaks is a verbatim quote with a link to the
   commit, PR, comment or agent-session prompt it came from. Code checks every quote against its source before it is shown, so
   the ghost cannot invent a reason.
4. **The medium** (Gemma) chooses and orders the quotes and adds short linking lines. Those lines are drawn
   in a different style and labelled as the medium's, never put in the ghost's mouth.
5. If the history holds no answer, the ghost says **"I never wrote down why."** and shows what it did find.
   That honest silence is a feature: it tells you to ask a living person, or to write the reason down.

A web app that works logged out. The Python backend and Gemma run on Render. (The Android APK was cut on
2026-10-30: the build started 13 hours before the deadline.)

This is a séance for **people's lost knowledge in a repo**, not a haunted terminal and not a tool that
channels dead languages. The post says so in its first lines.

## User

- **Who:** Tanay, a developer on a containers team. His team lead left about a month ago, and he keeps
  hitting code he wishes he could ask him about. That feeling opens the post, in Tanay's words. **Nothing
  from work goes into the code, data, evaluation, screenshots or post**: no employer, no code, no names.
- **Who else it is for:** anyone who inherits code from someone who moved on: open-source maintainers,
  new hires, the last person left on a team.
- **The moment:** you are about to delete a line that looks pointless. `git blame` shows a formatting
  commit from 2022. Before you delete it, you hold a séance.

## Evidence plan

**Question:** given a line of code, does the séance find the recorded reason it exists more often than
what an engineer does today?

**Dataset: deleted, then restored.** In big public repos, someone deleted code that looked pointless, it
broke something, and a revert put it back. Each revert is a real "why does this exist?" with the answer
written down.

- Mine commits like `Revert "Remove …"` (also "Delete", "Drop") from long-lived repos with GitHub PRs.
  Counts on 2026-10-27 for `Revert "Remove` alone: Kubernetes 66, Rails 80, moby 9, Prometheus 6. Final
  repos are chosen in design. Kubernetes stays in the set because it is the code Tanay knows best.
- Most revert messages say only "This reverts commit X", so the reason is usually in the revert's PR or a
  linked issue. Labelling reads those. A case is kept if they state a reason; the target is about 50
  cases.
- Each case gets a one-line reason, written by hand from the answer key, and an *answerable* label: does
  any history from before the deletion hold that reason?

**Held out by time.** Each method sees only commits, PRs and comments created before the deletion. The
deletion, the revert and everything after them are the answer key and are never input.

**Methods compared:**

| Method | What it sees | Stands for |
|--------|--------------|------------|
| B1 blame | Message of the commit that last touched the line | What most people do |
| B2 blame + PR | B1 plus that commit's PR description and review comments | A careful engineer clicking through |
| B3 log search | Top 5 messages from `git log -S` on the line's main identifier | Searching history by hand |
| Séance | Full line history, PRs, reviews, linked issues, read by Gemma | Ours |

**Metrics:**

- **Reason found** (main, graded blind to method by Claude, the agent that built it; Tanay re-grades 10
  random cases and the post reports how often we agree): does what the method shows you contain the reason
  from the answer key?
- **Reached the origin** (automatic): did it get past refactor and format commits to the commit that first
  wrote the line? This measures how often blame stops at the wrong commit.
- **Honest silence:** on unanswerable cases, how often does the séance say "I never wrote down why"
  instead of offering an unrelated quote as the reason?
- **Quote integrity:** quotes shown that are not verbatim in their source. This should be 0 by
  construction; we also report how many model outputs the checker had to reject.
- Séance against B2 with a paired bootstrap, as in Week 3.

**Limits we will state:**

- Reverts are a biased sample: they are code whose reason mattered enough to break something.
- The answer key is labelled by the author (Tanay); a second grader on a subset only if someone volunteers.
- "Answerable" is judged from the evidence the four methods surfaced, so a reason none of them found would
  be missed.
- About 50 cases from a few repos.

Possible title: "50 times someone deleted code nobody understood. The ghost knew why N times. git blame
knew M."

All numbers come from one command in `scripts/`, written to `results/`.

## First user

Tanay, on the morning of Saturday 2026-10-31, on public repos only (Kubernetes lines he is curious about first). We log
what he asked, whether the ghost answered, and whether he would have found the answer without it. If a
friend who codes tries it on a public repo, the post quotes them; if not, it says so.

## Prize categories

| Category | Build decision that justifies it |
|----------|----------------------------------|
| Gemma | The medium: picks the quotes that answer the question, orders them, writes the marked linking lines. It never writes the ghost's words |
| Render | Backend and Gemma (Ollama) run there from one Blueprint |
| Entire | Its brief is "search past agent work to explain why code exists". When a line's commit carries an `Entire-Checkpoint` trailer, the séance reads that session from the repo's `refs/entire/checkpoints/…` (plain git, no account) and the ghost can quote the author's own prompt. About 108,000 public commits carry the trailer (GitHub search, 2026-10-27), and repos such as `thedannywahl/pantoken` publish the refs. We also record this project's sessions with the Entire CLI and share them |

Not entered: ElevenLabs (a synthetic voice reading a real person's words crosses the guardrail below, and
it is a closed API); MongoDB Atlas and Tiger Data (the passages for one line fit in memory, so a database
would be decoration); .tech Domain (cut for time).

## Why open matters (for the post)

The repos that need this most are private: your team's code and your old lead's PRs. Many companies
cannot send those to a closed model. An open-weight model on your own machine or server can read them.
The public demo runs on public repos; the same code runs inside your network.

## Guardrails (real people)

- Public words only, always shown with a link to the source. Nothing paraphrased into their mouth.
- The person "left the project", never framed as dead. The ghost is a generic pixel ghost with their
  GitHub handle, not their photo.
- The demo gallery features people who simply moved on to other work. Anyone who asks is removed from it.

## Decisions

- **Backend:** Python (git tooling, Ollama client, evaluation stats reused from Week 3). **App:**
  TypeScript and Vite, wrapped with Capacitor, pixel art drawn as palette grids in code, as in Week 3.
- **Data:** public GitHub only. Clones in `data/raw/`, API responses cached in `data/cache/`, both
  git-ignored. No network in tests.
- **No GitHub token on the server.** Render holds no token of Tanay's. The backend clones public repos
  over plain git, which needs none, and walks the line history locally (a size cap keeps clones small;
  big repos such as Kubernetes appear through the gallery). PR, review and issue text is fetched by the
  visitor's own browser from `api.github.com`, unauthenticated: 60 calls an hour per visitor, enough for
  a few séances. A visitor may paste their own token for more; it stays in that browser tab, is sent only
  to `api.github.com`, and is never stored or sent to our backend. The gallery needs no calls at all.
- **Mining and evaluation run on Tanay's machine** through his existing `gh` login, read-only calls on
  public repos (Tanay agreed 2026-10-30). Nothing of it is deployed. Responses are cached so the
  evaluation reruns offline.
- **Agent sessions:** recorded with the Entire CLI for this repo. Before the repo or its checkpoint refs
  are made public, the transcripts are read through for anything from work; refs that hold any are
  dropped.
- **Demo:** a gallery of haunted lines from the evaluation set, precomputed so judges see a séance at
  once; live séances on any public repo, rate-limited.
- **Model:** Gemma through Ollama, the size settled in design (Week 3 ran Gemma 3 4B on Render 2c-4g).
  The crystal ball animation covers the CPU wait.
- **Tanay's part (2026-10-30):** no `@human` code tasks this week; Tanay was busy with work until the last
  night. Tanay's parts are the opening in his own words, the spot-check grading, the first-user session
  and publishing. No unlock game.
- **Repo:** `ouija-blame` on GitHub, private until Tanay makes it public.
- **Render:** web plus Ollama adds about $3.6 a day. Week 3's two services are suspended once its results
  are out.

## Non-goals

- Private repos or sign-in with GitHub in the hosted demo (Auth0 Token Vault would do this well, but not
  in 3½ days).
- GitLab, Gerrit or mailing-list history (excludes repos like the Go project).
- Answering questions about code in general; it answers only "why does this line exist".
- Writing new documentation or comments back into the repo.
- Voice, iOS, Play Store listing.

## Cut line

Deadline: Saturday 2026-10-31 12:29 IST. If time runs short, drop in this order:

Already cut on 2026-10-30: the APK, Tiger Data hybrid search, the .tech domain.

1. Entire checkpoint reading
2. live séances on any repo (keep the precomputed gallery)
3. animations (keep static scenes)

The revert dataset, the four-method evaluation, the quote checker and the ghost-or-silence answer are
never cut.

## Open questions

None.

## Changelog

- 2026-10-27: First draft after Tanay picked the séance idea. Web app plus APK with a pixel-art crystal
  ball, as Tanay suggested. Revert counts checked through the GitHub search API.
- 2026-10-27: Tanay's answers. Name: Ouija Blame. No token of Tanay's on Render: the server clones over
  plain git and visitors' browsers call the GitHub API, with an optional token of their own. Entire: the
  séance reads public checkpoint refs, and this repo's sessions are recorded with the Entire CLI. No
  unlock game. Repo `ouija-blame`. Week 3 services to be suspended when results are out.
- 2026-10-30: Build starts 13 hours before the deadline (2026-10-31 12:29 IST). Tanay agreed to build
  through without separate gates, Claude writing most of it. Cut the APK, Tiger Data and .tech. Mining
  uses Tanay's `gh` login locally. Claude grades blind, Tanay spot-checks 10. No `@human` code tasks.
