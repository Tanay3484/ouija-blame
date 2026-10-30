# Week 4 — Ghost in the Machine — agent guide

Hacktoberfest 2026 Week 4 entry, the last of the series. The master guide in `../CLAUDE.md` holds the
workflow and playbook; this file holds what is specific to this week.

**Product (picked 2026-10-27): "Séance With the Engineer Who Left"** (working name; pick a final name in the
brief). You highlight a cursed line in a repo, and it summons the ghost of whoever wrote it, rebuilt from
their real commits, PR discussions, review comments and linked issues. **The ghost can only speak in their
own recorded words, every claim linked to a commit, PR or comment**, so it can never invent a reason. If
history holds no answer, the ghost says "I never wrote down why." It answers the question that haunts
every legacy codebase: *why does this exist?*

Why Tanay picked it: his own team lead left about a month ago, and he keeps wishing he could ask him why
bits of code are the way they are. That feeling is the post's opening. **Nothing from work goes in the
code, data, evaluation, screenshots or post**: no employer name, no code, no colleague's name. Only the
feeling, in Tanay's words.

How the idea was reached (2026-10-27): round 1 (Ghost Runner on Fit activities, Link Rot Séance, faces in
photos, Night Shift) was "good but not the winning factor"; round 2 (searches-past ghost, Kubernetes
exorcist, unreadable letters, last voicemail) was not Halloween enough. Tanay asked for "a true nightmare
for software engineers". Round 3: The Hour That Happens Twice (DST, US clocks go back Sun 2026-11-01),
**Séance (picked)**, Ghost Packages (slopsquatting), Zombie Infrastructure. Keep the others as fallbacks.

## The challenge

- Page: <https://dev.to/challenges/hacktoberfest-week4-2026-10-26>. Partner descriptions:
  <https://dev.to/challenges/hf26>. **Fetch the submission template** from the challenge page or its
  announcement post before drafting the post; it was not read yet.
- Theme: **Ghost in the Machine**. Something spooky, or something that honours the past in the spirit of
  Día de los Muertos, with open-weight models or open-source AI at the core. Halloween is 2026-10-31.
- The post must say why open innovation matters for the build ("works with the internet off", "keeps data
  on your machine", "not locked in a service that might disappear", "where open beat closed").
- **Deadline: plan for Sat 2026-10-31 06:59 UTC = 12:29 IST.** The page text says "October 31, 11:59 PM
  PDT" (= 2026-11-01 06:59 UTC); the API's `ends_at` says 2026-10-31 06:59 UTC. Week 3 had the same
  mismatch. Use the earlier one. Winners the week of 2026-11-02.
- Judging, heaviest first: writing quality, relevance to prompt and theme, creativity, technical execution,
  partner tech (optional). If the app needs a login, give judges test credentials or instructions.
- Rules: one entry, a new project built in the window, tag `#hf26challenge` (plus `devchallenge`), one win
  per challenge. Saving the agent session with DevRelay is optional but "helps the judges".

### Already crowded (2026-10-27, first day): avoid looking like these

Haunted terminals (GhostInTheShell, HauntedTerminal, NecroShell, PhantomTerminal, Revenant), séances for
dead programming languages ("Seance: a terminal that channels dead programming languages"), ofrendas
("Ofrenda: a ghost that only knows what you tell it", "AI Buddies as a Digital Ofrenda"), ghost-story
generators from logs (Hauntlog). These are the page's own example ideas. Ours is a séance for *people's
lost knowledge in a repo*: say so early in the post, and never call it a terminal toy.

## Prize categories (21 winners)

Overall $250. Featured $200: Render, TabPFN, Tinker, Arduino, DigitalOcean, Gemma. Partner $100: Auth0 for
AI Agents, Backboard, Browserbase, ElevenLabs, Entire, GitHub Copilot, Mastra, MongoDB Atlas, Sentry Agent
Tracing, SerpApi, Temporal, Tiger Data, Ultramarine (Paper Instruments), .tech Domain.

Likely fits (check each against its hub description before committing): **Gemma** (reads the history and
joins the quotes), **Entire** (its brief includes "search past agent work to explain why code exists",
nearly our product), **MongoDB Atlas** or **Tiger Data** (search commits and PR comments by meaning),
**Render** (host it; won in Week 1). Week 2 and Week 3 results: Holdfast won nothing in Week 2; Week 3
results pending at the time of writing.

## Evidence plan (draft; goes into the brief)

- **Claim:** given a line of code, the ghost finds the recorded reason it exists more often than what an
  engineer does today (read the `git blame` commit message, or `git log -S`/`-G` search).
- **Dataset: reverts in real public repos.** Someone deleted code nobody understood, it broke, and a revert
  commit says why it was needed. Each revert is a ready-made "why does this exist?" with the answer. Mine
  ~50 from large, long-lived repos; keep the ones whose revert message (or linked issue) states a reason.
- **Held out by time:** the ghost sees only history from *before* the deletion. The revert and anything
  after it are the answer key, never input.
- **Metrics:** citation hit (did it retrieve the commit, PR or comment that holds the reason: automatic),
  and reason match (does its explanation give the revert's reason: hand-graded on a small set by Tanay).
  Plus "I never wrote down why" honesty: on lines whose history really has no reason, does it say so?
- **Baselines:** the blame commit message alone; keyword search over the log.
- **First user:** Tanay, on public repos (never work code). A second user if anyone tries it from the post.
- Possible title shape: "50 times someone deleted code nobody understood. The ghost knew why N times.
  git blame knew M."

## Data plan

- Public GitHub only. Clone repos into `data/raw/` (git-ignored) for blame and log; PRs, reviews and issues
  from the GitHub API (REST or GraphQL), cached in `data/cache/` (git-ignored). No network in tests.
- A GitHub token, if needed for rate limits, lives in `.env` (git-ignored) and needs no scopes for public
  reads. Ask Tanay before using or creating one.
- Finding "engineers who left": published truck-factor research lists projects and core developers who
  stopped contributing; or find them by history (wrote most of a file, no commits anywhere for 3+ years).
- **Guardrails, because these are real people:** their public words only, always cited with a link; text
  the model adds is visibly marked as the model's, never put in the engineer's mouth; "left the project",
  never framed as dead; prefer people who simply moved on.

## Workflow state

- 2026-10-27: folder set up (git repo, `specs/README.md`, `.claude/agents/` task-coach, spec-writer,
  post-writer, `.gitignore`). No GitHub repo yet: ask Tanay for the repo name, create it, make it public
  only when Tanay says so (Tanay may need to do it himself; the classifier blocked the agent in Week 3),
  then apply branch protection like Week 3 (PR, 1 approval, `tests` check, no force pushes).
- 2026-10-27: brief drafted. Name **Ouija Blame**. Private repo <https://github.com/Tanay3484/ouija-blame>
  created and `main` pushed (branch protection once public). Tanay's answers: no token of his on Render
  (server clones over plain git; visitors' browsers call the GitHub API, optional own token kept in the
  tab); Entire is in (séance reads public `refs/entire/checkpoints/…`; Tanay installs the CLI to record
  sessions; read transcripts for work content before anything goes public); no unlock game (no time).
- **Next:** Tanay answers the local-token question and approves the brief; then requirements, design,
  tasks, each approved by Tanay.
- Good `@human` candidates (pure functions, 1–3 h each): the revert miner (find reverts and pair them with
  the deleted lines), the blame-to-PR linker (line → commit → PR → review threads), the citation checker
  (does every quoted span exist verbatim in the cited source?), the evaluation statistics (hit rates and a
  paired bootstrap, as in Week 3).

## Carried over from Week 3 (things that bit us)

- Tanay merges PRs within minutes: check a PR is still open before pushing to its branch; follow-ups go on
  a fresh branch from `origin/main`. Never edit a merged PR to describe new work.
- Test every user-facing flow in a real browser with real data before calling it done. Week 3's demo
  trapped users in demo mode and an import silently changed nothing; both were found by Tanay, not tests.
- Every number in the post comes from a script and a file in `results/`. Drafts in `drafts/` (git-ignored).
  Tanay publishes; never post for him, never make the repo public or publish a release for him.
- Render credit is nearly used up and the card takes the overflow. Check the running cost before adding a
  service, and remind Tanay to suspend Week 1–3 services when their results are out.
- Windows, Git Bash and PowerShell. Run Python that reads downloaded data with `-I`.
