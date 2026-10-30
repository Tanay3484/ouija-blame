import { fetchAll, repoSizeKb, type LineLink } from "./github";
import type { GalleryItem, Seance, WalkOut } from "./types";

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) {
    let msg = `The séance failed (${r.status}).`;
    try {
      const j = await r.json();
      if (j.detail) msg = typeof j.detail === "string" ? j.detail : msg;
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export async function gallery(): Promise<GalleryItem[]> {
  const r = await fetch("./gallery/index.json");
  return r.ok ? r.json() : [];
}

export async function gallerySeance(id: string): Promise<Seance> {
  const r = await fetch(`./gallery/${encodeURIComponent(id)}.json`);
  if (!r.ok) throw new Error("That séance is missing from the gallery.");
  return r.json();
}

/** A live séance: walk on the server, GitHub calls from this browser, the medium on the server. */
export async function liveSeance(link: LineLink, say: (line: string) => void): Promise<Seance> {
  say(`Asking GitHub how big ${link.owner}/${link.repo} is…`);
  const size_kb = await repoSizeKb(link.owner, link.repo);
  say("Cloning the repo and walking the line back through time…");
  const walk = await post<WalkOut>("/api/walk", { ...link, size_kb });
  const first = walk.commits[walk.commits.length - 1];
  say(`${walk.commits.length} commit${walk.commits.length === 1 ? "" : "s"} touched this line. The first was by ${first.author}, ${first.date.slice(0, 10)}.`);
  const github: Record<string, unknown> = {};
  let need = walk.need;
  for (let round = 0; round < 4 && need.length; round++) {
    await fetchAll(need, github, (p) => say(`Reading ${p.replace(/^repos\/[^/]+\/[^/]+\//, "")}…`));
    need = (await post<{ need: string[] }>("/api/plan", { walk_id: walk.walk_id, github })).need;
  }
  say("The medium is listening. Gemma runs on a small CPU, so this can take a minute…");
  return post<Seance>("/api/seance", { walk_id: walk.walk_id, github });
}
