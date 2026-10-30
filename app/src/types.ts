export interface Quote {
  text: string;
  author: string;
  kind: string;
  url: string;
  created: string;
  title: string;
  source_id: string;
  is_ghost: boolean;
}

export interface Seance {
  repo: string;
  path: string;
  line: number;
  line_text: string;
  ghost: {
    name: string;
    login: string | null;
    first_wrote: string;
    commit: string;
    commit_url: string;
    subject: string;
    last_seen: string | null;
  };
  blame: { commit: string; subject: string; author: string; date: string; url: string };
  silent: boolean;
  silence: string | null;
  quotes: Quote[];
  medium: string;
  /** Gemma's plain-words answer, written from the checked quotes; null on old séances. */
  card?: { what: string; why: string; next: string; cites: number[]; error: string | null } | null;
  stats: {
    commits_walked: number;
    sources: number;
    passages: number;
    shown_to_model: number;
    dropped_by_checker: number;
    model_error: string | null;
  };
  /** Only on gallery séances, which come from the evaluation: what happened after. */
  case?: { id: string; revert: string; deletion: string; deletion_subject: string; cutoff: string };
  revert_subject?: string;
  answer?: string;
  /** Demo séances outside the evaluation say what they are. */
  note?: string;
}

export interface GalleryItem {
  id: string;
  repo: string;
  path: string;
  line_text: string;
  deletion_subject: string;
  revert_subject: string;
  deleted_on: string;
  ghost: string;
  silent: boolean;
}

export interface WalkOut {
  walk_id: string;
  line_text: string;
  commits: { sha: string; author: string; date: string; subject: string }[];
  need: string[];
}
