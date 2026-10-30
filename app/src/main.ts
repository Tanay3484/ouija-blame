import "@fontsource/press-start-2p";
import "@fontsource/vt323";
import "./style.css";
import { gallery, gallerySeance, liveSeance } from "./api";
import { Scene } from "./art";
import { parseLineUrl, RateLimited, setToken } from "./github";
import { Ouija, type Spot } from "./ouija";
import type { GalleryItem, Quote, Seance } from "./types";

const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T;

const KIND: Record<string, string> = {
  commit: "commit message",
  pr: "pull request",
  pr_comment: "PR comment",
  review_comment: "code review comment",
  review: "review",
  issue: "issue",
  issue_comment: "issue comment",
  checkpoint: "agent session prompt",
};

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** Only links to GitHub are ever rendered: the text comes from strangers on the internet. */
function link(href: string, text: string): HTMLElement {
  if (!/^https:\/\/github\.com\//.test(href)) return el("span", "", text);
  const a = el("a", "", text);
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  return a;
}

const day = (iso: string | null | undefined) => (iso ? iso.slice(0, 10) : "?");
const month = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("en", { month: "long", year: "numeric", timeZone: "UTC" }) : "?";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const wide = () => matchMedia("(min-width: 1000px)").matches;

const scene = new Scene($<HTMLCanvasElement>("#scene"));
const board = new Ouija($<HTMLCanvasElement>("#ouija"), { onRest: (s) => void onBoard(s) });

const log = $<HTMLOListElement>("#log");
function say(line: string) {
  log.append(el("li", "", line));
  while (log.children.length > 5) log.firstElementChild?.remove();
}

async function type(target: HTMLElement, text: string) {
  if (reduced || text.length > 900) {
    target.textContent = text;
    return;
  }
  target.textContent = "";
  const step = Math.max(1, Math.floor(text.length / 140));
  for (let i = 0; i < text.length; i += step) {
    target.textContent = text.slice(0, i + step);
    await sleep(12);
  }
}

// ---- Views: the gallery (home) or one séance ------------------------------------------------------

const home = $<HTMLElement>("#home");
const answer = $<HTMLElement>("#answer");

function showHome() {
  answer.hidden = true;
  answer.replaceChildren();
  home.hidden = false;
  scene.set("idle");
  if (location.hash) history.replaceState(null, "", location.pathname);
}

function showAnswerView() {
  home.hidden = true;
  answer.hidden = false;
  answer.replaceChildren();
  if (!wide()) $("#altar").scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  else window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
}

function backButton(): HTMLElement {
  const b = el("button", "ghostly", "← All haunted lines");
  b.type = "button";
  b.addEventListener("click", () => goodbye());
  return b;
}

// ---- Rendering a séance ----------------------------------------------------------------------------

async function show(s: Seance, opts: { replay: boolean }) {
  const who = s.ghost.login ? `@${s.ghost.login}` : s.ghost.name;

  const top = el("div", "answer-top");
  top.append(backButton());
  answer.append(top);

  const head = el("div", "box");
  head.append(el("p", "kicker", `${s.repo} · ${s.path}:${s.line}`));
  head.append(el("pre", "code", s.line_text.trim()));
  answer.append(head);

  if (opts.replay) {
    scene.set("summoning");
    board.wander();
    say(`Walking line ${s.line} of ${s.path.split("/").pop()} back through time…`);
    await sleep(reduced ? 0 : 800);
    say(`${s.stats.commits_walked} commit${s.stats.commits_walked === 1 ? "" : "s"} touched it. The first was by ${s.ghost.name}, ${day(s.ghost.first_wrote)}.`);
    await sleep(reduced ? 0 : 800);
    say(`Gathered ${s.stats.sources} things they and others wrote: ${s.stats.passages} passages.`);
    await sleep(reduced ? 0 : 800);
    say(`The medium read the ${s.stats.shown_to_model} closest passages and chose ${s.quotes.length || "none"}.`);
    await sleep(reduced ? 0 : 700);
  }
  scene.set(s.silent ? "silent" : "speaking");
  if (s.silent) board.say("NO");
  else board.spell(s.ghost.login || s.ghost.name.split(" ")[0], "YES");
  say(s.silent ? "The ghost has nothing written to say." : `${who} answers.`);

  answer.append(verdict(s));

  const ghost = el("div", "box ghost-card");
  ghost.append(el("p", "kicker", "The ghost"));
  ghost.append(el("h2", "", who));
  const meta = el("p", "meta");
  meta.append("First wrote this line on ", el("strong", "", day(s.ghost.first_wrote)), " in ");
  meta.append(link(s.ghost.commit_url, `“${s.ghost.subject}”`), ".");
  if (s.ghost.last_seen) meta.append(` Last seen in this repo: ${month(s.ghost.last_seen)}.`);
  ghost.append(meta);
  if (s.note) ghost.append(el("p", "meta held-out", s.note));
  if (s.case) ghost.append(el("p", "meta held-out", `This séance heard only what was written before ${day(s.case.cutoff)}, the day someone deleted this line.`));
  answer.append(ghost);

  if (s.silent) {
    const b = el("blockquote", "bubble silent");
    answer.append(b);
    await type(b, s.silence || "I never wrote down why.");
  } else {
    const seen = new Map<string, number>();
    for (const [i, q] of s.quotes.entries()) {
      const keyText = q.text.replace(/\s+/g, " ").trim();
      const first = seen.get(keyText);
      if (first !== undefined) {
        // A reviewer repeating the same words: say so in one line instead of showing them twice.
        const p = el("p", "echo");
        p.id = `q${i + 1}`;
        p.append(`[${i + 1}] the same words as [${first}], also posted by @${q.author} in a `, link(q.url, KIND[q.kind] ?? q.kind), ".");
        answer.append(p);
        continue;
      }
      seen.set(keyText, i + 1);
      await quote(q, i + 1, who);
    }
  }

  const blame = el("div", "box blame");
  blame.append(el("p", "kicker", "What git blame shows you"));
  const bl = el("p");
  bl.append(link(s.blame.url, `“${s.blame.subject}”`), ` by ${s.blame.author}, ${day(s.blame.date)}`);
  blame.append(bl);
  blame.append(
    el(
      "p",
      "meta",
      s.blame.commit === s.ghost.commit
        ? "Here blame and the ghost agree on who wrote it; the séance adds what they and their reviewers wrote about it."
        : `Blame stops at the last change. The séance walked ${s.stats.commits_walked - 1} more change${s.stats.commits_walked === 2 ? "" : "s"} back to who first wrote it.`,
    ),
  );
  answer.append(blame);

  if (s.case) {
    const after = el("div", "box aftermath");
    after.append(el("p", "kicker", "What happened next"));
    const p = el("p");
    p.append(`On ${day(s.case.cutoff)} someone deleted it: `, link(`https://github.com/${s.repo}/commit/${s.case.deletion}`, `“${s.case.deletion_subject}”`), ". It broke, and it was put back: ");
    p.append(link(`https://github.com/${s.repo}/commit/${s.case.revert}`, `“${s.revert_subject ?? "the revert"}”`), ".");
    after.append(p);
    if (s.answer) after.append(el("p", "meta", `Why it had to come back (our one-line summary of the revert): ${s.answer}`));
    answer.append(after);
  }
}

/** The answer card: what the line does, why it exists (cited), and what to check before changing it. */
function verdict(s: Seance): HTMLElement {
  const box = el("section", "box verdict");
  box.setAttribute("aria-label", "The answer");
  box.append(el("h2", "", s.silent ? "The history is silent" : "What the history says"));
  const c = s.card;
  const dl = el("dl");
  const row = (label: string, body: HTMLElement | string) => {
    dl.append(el("dt", "", label));
    const dd = el("dd");
    dd.append(body);
    dl.append(dd);
  };
  if (c && !c.error) {
    if (c.what) row("What the line does", c.what);
    row("Why it exists", withCites(c.why, s.quotes.length));
    if (c.next) row("Before you change it", c.next);
  } else if (s.silent) {
    row("Why it exists", "Nobody wrote down why this line exists, at least not anywhere the séance could reach.");
    row("Before you change it", "Ask someone who still works on this code, check the tests, and write the reason next to the line.");
  } else {
    row("Why it exists", "The medium could not write a summary this time. The quotes below are the evidence; read them in order.");
  }
  box.append(dl);
  box.append(
    el(
      "p",
      "by",
      "Written by the medium, Gemma (an open-weight model), from the quotes below only. Each [n] jumps to the quote it rests on; a reason that cites nothing is not shown.",
    ),
  );
  return box;
}

function withCites(text: string, n: number): HTMLElement {
  const span = el("span");
  for (const part of text.split(/(\[\d+\])/)) {
    const m = /^\[(\d+)\]$/.exec(part);
    if (m && Number(m[1]) >= 1 && Number(m[1]) <= n) {
      const a = el("a", "cite", m[1]);
      a.href = `#q${m[1]}`;
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const t = document.getElementById(`q${m[1]}`);
        t?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" });
        t?.classList.add("flash");
        setTimeout(() => t?.classList.remove("flash"), 1400);
      });
      span.append(a);
    } else if (part) span.append(part);
  }
  return span;
}

async function quote(q: Quote, n: number, ghost: string): Promise<void> {
  const wrap = el("figure", q.is_ghost ? "quote" : "quote other");
  wrap.id = `q${n}`;
  const label = el("p", "kicker");
  label.append(el("span", "num", `[${n}]`), q.is_ghost ? "The ghost" : "Another voice in the room");
  wrap.append(label);
  const b = el("blockquote", "bubble");
  wrap.append(b);
  const cap = el("figcaption");
  cap.append(`— ${q.is_ghost ? ghost : "@" + q.author.replace(/^@/, "")}, `, link(q.url, `${KIND[q.kind] ?? q.kind}${q.title ? `: ${q.title}` : ""}`), `, ${day(q.created)}`);
  wrap.append(cap);
  answer.append(wrap);
  await type(b, q.text);
}

// ---- Gallery ------------------------------------------------------------------------------------

let items: GalleryItem[] = [];
let spelled = "";

const letters = (s: string) => s.toUpperCase().replace(/[^A-Z]/g, "");
function matches(it: GalleryItem, word: string): boolean {
  if (!word) return true;
  const [owner, name] = it.repo.split("/");
  return [owner, name].some((p) => letters(p).startsWith(word));
}

function renderGallery() {
  const grid = $<HTMLElement>("#gallery-grid");
  grid.replaceChildren();
  const word = spelled.length >= 2 ? spelled : "";
  const shown = items.filter((it) => matches(it, word));
  for (const it of shown) grid.append(card(it));
  const f = $<HTMLElement>("#gallery-filter");
  f.hidden = !word;
  f.textContent = shown.length ? `spelled ${word}: ${shown.length} line${shown.length === 1 ? "" : "s"} · rest on NO to clear` : `no ghosts answer to ${word} · rest on NO to clear`;
  if (!items.length) grid.append(el("p", "note", "The gallery is empty."));
}

function card(it: GalleryItem): HTMLElement {
  const b = el("button", "card");
  b.type = "button";
  b.append(el("p", "kicker", it.deleted_on ? `${it.repo} · deleted ${it.deleted_on.slice(0, 4)}` : `${it.repo} · written with an AI agent`));
  b.append(el("pre", "code", it.line_text.trim()));
  b.append(el("p", "card-sub", `“${it.deletion_subject}”`));
  b.append(el("p", "card-ghost", it.silent ? "The ghost stays silent" : `Summon ${it.ghost}`));
  b.addEventListener("click", () => void runGallery(it.id));
  return b;
}

let busy = false;
async function runGallery(id: string) {
  if (busy) return;
  busy = true;
  history.replaceState(null, "", `#seance=${id}`);
  log.replaceChildren();
  showAnswerView();
  try {
    await show(await gallerySeance(id), { replay: true });
  } catch (e) {
    say((e as Error).message);
    scene.set("idle");
  } finally {
    busy = false;
  }
}

// ---- Live séance --------------------------------------------------------------------------------

/** Run a live séance on the pasted link. False if no link was pasted. */
async function runLive(): Promise<boolean> {
  const err = $<HTMLElement>("#ask-error");
  err.textContent = "";
  const raw = $<HTMLInputElement>("#line-url").value;
  if (!raw.trim()) return false;
  const parts = parseLineUrl(raw);
  if (!parts) {
    err.textContent = "That is not a link to one line. Open a file on GitHub, click a line number, and copy the address.";
    return true;
  }
  if (busy) return true;
  setToken($<HTMLInputElement>("#token").value);
  busy = true;
  log.replaceChildren();
  scene.set("summoning");
  board.wander();
  showAnswerView();
  answer.append(backButton(), el("p", "note", "The séance has begun. Watch the table: each step appears under the crystal ball."));
  try {
    const s = await liveSeance(parts, say);
    answer.replaceChildren();
    await show(s, { replay: false });
  } catch (e) {
    scene.set("idle");
    board.say("NO");
    answer.replaceChildren();
    answer.append(backButton(), el("p", "error", e instanceof RateLimited ? `${e.message} Add your own token, or open a séance from the gallery.` : (e as Error).message));
    say("The spirits did not answer.");
  } finally {
    busy = false;
  }
  return true;
}

$<HTMLFormElement>("#ask").addEventListener("submit", (ev) => {
  ev.preventDefault();
  void runLive().then((ran) => {
    if (!ran) $<HTMLElement>("#ask-error").textContent = "Paste a GitHub link to one line first, or open a haunted line below.";
  });
});

// ---- The board as a control ---------------------------------------------------------------------

function goodbye() {
  spelled = "";
  $<HTMLElement>("#spelled").textContent = "";
  log.replaceChildren();
  showHome();
  renderGallery();
}

async function onBoard(spot: Spot) {
  const out = $<HTMLElement>("#spelled");
  if (spot === "YES") {
    if (busy) return;
    say("You asked the spirits to speak.");
    if (await runLive()) return;
    const pool = items.filter((it) => matches(it, spelled.length >= 2 ? spelled : "") && !it.silent);
    const pick = pool[Math.floor(Math.random() * pool.length)] ?? items[0];
    if (pick) void runGallery(pick.id);
    return;
  }
  if (spot === "NO") {
    spelled = "";
    out.textContent = "";
    say("The board is cleared.");
    if (!home.hidden) renderGallery();
    return;
  }
  if (spot === "GOODBYE") {
    if (!busy) goodbye();
    return;
  }
  spelled = (spelled + spot).slice(-10);
  out.textContent = spelled;
  if (!home.hidden) renderGallery();
}

/** `#seance=<id>` opens a gallery séance directly, so a séance can be linked from the post. */
function fromHash() {
  const m = /^#seance=([\w.-]+)$/.exec(location.hash);
  if (m) void runGallery(m[1]);
}
window.addEventListener("hashchange", fromHash);

void gallery().then((g) => {
  items = g;
  renderGallery();
  fromHash();
});
