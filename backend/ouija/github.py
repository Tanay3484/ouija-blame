"""A disk-cached GitHub REST client, for the evaluation only. The server never holds a token.

Every response is stored under `cache_dir` by path, so a rerun of the evaluation makes no calls. A 404 is
cached as None. Lists are fetched to at most `max_pages` pages of 100.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import httpx

_LIST_SUFFIXES = ("/comments", "/reviews", "/pulls")


def gh_token() -> str | None:
    """The token of the local `gh` login, if there is one (Tanay agreed to this for local mining)."""
    if tok := os.environ.get("GITHUB_TOKEN"):
        return tok
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


class CachedGitHub:
    def __init__(self, cache_dir: str, token: str | None = None, max_pages: int = 3) -> None:
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_pages = max_pages
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(base_url="https://api.github.com", headers=headers, timeout=30)
        self.calls = 0

    def _file(self, path: str) -> Path:
        return self.dir / (hashlib.sha1(path.encode()).hexdigest()[:20] + ".json")

    def __contains__(self, path: str) -> bool:
        return True  # the client can always fetch what it lacks

    def get(self, path: str, default=None):
        f = self._file(path)
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))["data"]
        data = self._fetch(path)
        f.write_text(json.dumps({"path": path, "data": data}), encoding="utf-8")
        return data if data is not None else default

    def _fetch(self, path: str):
        is_list = path.endswith(_LIST_SUFFIXES)
        items: list = []
        for page in range(1, (self.max_pages if is_list else 1) + 1):
            params = {"per_page": 100, "page": page} if is_list else None
            for attempt in range(4):
                self.calls += 1
                r = self._http.get("/" + path, params=params)
                if r.status_code in (403, 429) and "rate limit" in r.text.lower():
                    reset = int(r.headers.get("x-ratelimit-reset", time.time() + 60))
                    time.sleep(max(5, min(900, reset - time.time() + 2)))
                    continue
                if r.status_code >= 500 and attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            if r.status_code in (404, 410, 422):
                return None
            r.raise_for_status()
            data = r.json()
            if not is_list:
                return data
            items.extend(data)
            if len(data) < 100:
                break
        return items
