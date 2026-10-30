// GitHub API calls made by the visitor's own browser, so our server never holds a token.
// Without a token GitHub allows 60 calls an hour per visitor; a token pasted by the visitor stays in
// this tab's memory, is sent only to api.github.com, and never reaches our backend.

const API = "https://api.github.com/";
const LIST = /\/(comments|reviews|pulls)$/;

let token: string | null = null;
export function setToken(t: string | null): void {
  token = t && t.trim() ? t.trim() : null;
}

export class RateLimited extends Error {}

export interface LineLink {
  owner: string;
  repo: string;
  ref: string;
  path: string;
  line: number;
}

const LINE_URL = /github\.com\/([\w.-]+)\/([\w.-]+)\/blob\/([^/]+)\/([^#?]+)#L(\d+)/;

export function parseLineUrl(url: string): LineLink | null {
  const m = LINE_URL.exec(url.trim());
  if (!m) return null;
  return { owner: m[1], repo: m[2].replace(/\.git$/, ""), ref: m[3], path: decodeURIComponent(m[4]), line: Number(m[5]) };
}

async function get(path: string): Promise<unknown> {
  const headers: Record<string, string> = { Accept: "application/vnd.github+json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const url = API + path + (LIST.test(path) ? "?per_page=100" : "");
  const r = await fetch(url, { headers });
  if (r.status === 403 || r.status === 429) {
    if (r.headers.get("x-ratelimit-remaining") === "0") throw new RateLimited("GitHub's hourly limit for this browser is used up.");
  }
  if (r.status === 404 || r.status === 410 || r.status === 422) return null;
  if (!r.ok) throw new Error(`GitHub said ${r.status} for ${path}`);
  return r.json();
}

/** Keep only the fields the séance reads, so the request to our server stays small. */
function slim(v: unknown): unknown {
  const one = (o: Record<string, any>) => ({
    id: o.id,
    number: o.number,
    title: o.title,
    body: o.body,
    html_url: o.html_url,
    created_at: o.created_at,
    submitted_at: o.submitted_at,
    merged_at: o.merged_at,
    state: o.state,
    path: o.path,
    user: o.user ? { login: o.user.login, type: o.user.type } : null,
  });
  if (Array.isArray(v)) return v.map((x) => one(x));
  if (v && typeof v === "object") return one(v as Record<string, any>);
  return v;
}

export async function fetchAll(paths: string[], into: Record<string, unknown>, onEach?: (p: string) => void): Promise<void> {
  for (const p of paths) {
    if (p in into) continue;
    onEach?.(p);
    into[p] = slim(await get(p));
  }
}

export async function repoSizeKb(owner: string, repo: string): Promise<number | null> {
  const r = (await get(`repos/${owner}/${repo}`)) as { size?: number } | null;
  return r?.size ?? null;
}
