import "@fontsource/press-start-2p";
import "@fontsource/vt323";
import "./style.css";
import { gallery, gallerySeance, liveSeance } from "./api";
import { Ouija, Scene } from "./art";
import { parseLineUrl, RateLimited, setToken } from "./github";
import type { GalleryItem, Quote, Seance } from "./types";

const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T;

const scene = new Scene($<HTMLCanvasElement>("#scene"));
const board = new Ouija($<HTMLCanvasElement>("#ouija"));
board.wander();

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
const month = (iso: string | null | undefined) => {
  if (!iso) return "?";
  const d = new Date(iso);
  return d.toLocaleString("en", { month: "long", year: "numeric", timeZone: "UTC" });
};
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

const log = $<HTMLOListElement>("#log");
function say(line: string) {
  const li = el("li", "", line);
  log.append(li);
  while (log.children.length > 6) log.firstElementChild?.remove();
}

async function type(target: HTMLElement, text: string) {
  if (reduced || text.length > 900) {
    target.textContent = text;
    return;
  }
  target.textContent = "";
  const step = Math.max(1, Math.floor(text.length / 160));
  for (let i = 0; i < text.length; i += step) {
    target.textContent = text.slice(0, i + step);
    await sleep(14);
  }
}

// ---- Rendering a séance -----------------------------------------------------------------------

async function show(s: Seance, opts: { replay: boolean }) {
  const out = $<HTMLElement>("#answer");
  out.replaceChildren();
  out.hidden = false;
  const who = s.ghost.login ? `@${s.ghost.login}` : s.ghost.name;

  const head = el("div", "line-card");
  head.append(el("p", "kicker", `${s.repo} · ${s.path}:${s.line}`));
  head.append(el("pre", "code", s.line_text.trim()));
  out.append(head);

  if (opts.replay) {
    scene.set("summoning");
    board.wander();
    say(`Walking line ${s.line} of ${s.path.split("/").pop()} back through time…`);
    await sleep(reduced ? 0 : 900);
    say(`${s.stats.commits_walked} commit${s.stats.commits_walked === 1 ? "" : "s"} touched it. The first was by ${s.ghost.name}, ${day(s.ghost.first_wrote)}.`);
    await sleep(reduced ? 0 : 900);
    say(`Gathered ${s.stats.sources} things they and others wrote: ${s.stats.passages} passages.`);
    await sleep(reduced ? 0 : 900);
    say(`The medium read the ${s.stats.shown_to_model} closest passages…`);
    await sleep(reduced ? 0 : 1100);
  }

  scene.set(s.silent ? "silent" : "speaking");
  if (s.silent) board.say("NO");
  else board.spell(s.ghost.login || s.ghost.name.split(" ")[0], "YES");

  const ghost = el("div", "ghost-card");
  ghost.append(el("p", "kicker", "The ghost"));
  const name = el("h2", "", who);
  ghost.append(name);
  const meta = el("p", "meta");
  meta.append("First wrote this line on ", el("strong", "", day(s.ghost.first_wrote)), " in ");
  meta.append(link(s.ghost.commit_url, `“${s.ghost.subject}”`), ".");
  if (s.ghost.last_seen) meta.append(` Last seen in this repo: ${month(s.ghost.last_seen)}.`);
  ghost.append(meta);
  if (s.case) {
    ghost.append(el("p", "meta held-out", `This séance only heard what was written before ${day(s.case.cutoff)}, the day someone deleted this line.`));
  }
  out.append(ghost);

  if (s.silent) {
    const b = el("blockquote", "bubble silent");
    out.append(b);
    await type(b, s.silence || "I never wrote down why.");
    out.append(el("p", "note", "Nothing in this line's history says why it exists. Ask someone who is still here, and then write the reason down where the next person will find it."));
  } else {
    for (const q of s.quotes) await quote(q, who);
    if (s.medium) {
      const m = el("div", "medium");
      m.append(el("p", "kicker", "The medium (Gemma, an open-weight model) adds, in its own words:"));
      m.append(el("p", "", s.medium));
      out.append(m);
    }
  }

  const blame = el("div", "blame");
  blame.append(el("p", "kicker", "What git blame shows you"));
  const bl = el("p");
  bl.append(link(s.blame.url, `“${s.blame.subject}”`), ` by ${s.blame.author}, ${day(s.blame.date)}`);
  blame.append(bl);
  if (s.blame.commit === s.ghost.commit) blame.append(el("p", "meta", "Here blame and the ghost agree on who wrote it."));
  else blame.append(el("p", "meta", `Blame stops at the last change. The line is older: the séance walked ${s.stats.commits_walked - 1} more change${s.stats.commits_walked === 2 ? "" : "s"} back.`));
  out.append(blame);

  if (s.case) {
    const after = el("div", "aftermath");
    after.append(el("p", "kicker", "What happened next"));
    const p = el("p");
    p.append(`On ${day(s.case.cutoff)} someone deleted it: `, link(`https://github.com/${s.repo}/commit/${s.case.deletion}`, `“${s.case.deletion_subject}”`), ". It broke, and it was put back: ");
    p.append(link(`https://github.com/${s.repo}/commit/${s.case.revert}`, `“${s.revert_subject ?? "the revert"}”`), ".");
    after.append(p);
    if (s.answer) after.append(el("p", "meta", `Why it was needed, from the revert (our one-line summary): ${s.answer}`));
    out.append(after);
  }
  if (s.stats.dropped_by_checker) out.append(el("p", "note", `The quote checker threw out ${s.stats.dropped_by_checker} passage(s) that did not match their source word for word.`));
  out.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
}

async function quote(q: Quote, ghost: string): Promise<void> {
  const wrap = el("figure", q.is_ghost ? "quote" : "quote other");
  if (!q.is_ghost) wrap.append(el("p", "kicker", "Another voice in the room"));
  const b = el("blockquote", "bubble");
  wrap.append(b);
  const cap = el("figcaption");
  cap.append(`— ${q.is_ghost ? ghost : "@" + q.author.replace(/^@/, "")}, `, link(q.url, `${KIND[q.kind] ?? q.kind}${q.title ? `: ${q.title}` : ""}`), `, ${day(q.created)}`);
  wrap.append(cap);
  $<HTMLElement>("#answer").append(wrap);
  await type(b, q.text);
}

// ---- Gallery ------------------------------------------------------------------------------------

async function loadGallery() {
  const items = await gallery();
  const grid = $<HTMLElement>("#gallery-grid");
  grid.replaceChildren();
  for (const it of items) grid.append(card(it));
  if (!items.length) grid.append(el("p", "note", "The gallery is empty."));
}

function card(it: GalleryItem): HTMLElement {
  const b = el("button", "card");
  b.type = "button";
  b.append(el("p", "kicker", `${it.repo} · deleted ${it.deleted_on.slice(0, 4)}`));
  b.append(el("pre", "code", it.line_text.trim()));
  b.append(el("p", "card-sub", `“${it.deletion_subject}”`));
  b.append(el("p", "card-ghost", it.silent ? "The ghost stays silent" : `Summon ${it.ghost}`));
  b.addEventListener("click", () => {
    history.replaceState(null, "", `#seance=${it.id}`);
    void runGallery(it.id);
  });
  return b;
}

let busy = false;
async function runGallery(id: string) {
  if (busy) return;
  busy = true;
  log.replaceChildren();
  $("#altar").scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
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

$<HTMLFormElement>("#ask").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (busy) return;
  const url = $<HTMLInputElement>("#line-url").value;
  const linkParts = parseLineUrl(url);
  const err = $<HTMLElement>("#ask-error");
  err.textContent = "";
  if (!linkParts) {
    err.textContent = "Paste a GitHub link to one line: open a file on GitHub, click a line number, and copy the address.";
    return;
  }
  setToken($<HTMLInputElement>("#token").value);
  busy = true;
  log.replaceChildren();
  $<HTMLElement>("#answer").hidden = true;
  scene.set("summoning");
  board.wander();
  $("#altar").scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  try {
    const s = await liveSeance(linkParts, say);
    await show(s, { replay: false });
  } catch (e) {
    scene.set("idle");
    board.say("GOODBYE");
    say(e instanceof RateLimited ? `${e.message} Add your own token below, or open a séance from the gallery.` : (e as Error).message);
  } finally {
    busy = false;
  }
});

/** `#seance=<id>` opens a gallery séance directly, so a séance can be linked from the post. */
function fromHash() {
  const m = /^#seance=([\w.-]+)$/.exec(location.hash);
  if (m) void runGallery(m[1]);
}
window.addEventListener("hashchange", fromHash);

void loadGallery().then(fromHash);
