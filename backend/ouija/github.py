"""A disk-cached GitHub REST client, for the evaluation only. The server never holds a token.

Calls go through the local `gh` CLI (`gh api`), so the evaluation uses Tanay's existing login without
the token ever passing through this code (Tanay agreed to the `gh` login for local mining).

Every response is stored under `cache_dir` by path, so a rerun of the evaluation makes no calls. A 404 is
cached as None. Lists are fetched to at most `max_pages` pages of 100.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

_LIST_SUFFIXES = ("/comments", "/reviews", "/pulls")


class GitHubError(Exception):
    pass


class CachedGitHub:
    def __init__(self, cache_dir: str, max_pages: int = 3, offline: bool = False) -> None:
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_pages = max_pages
        self.offline = offline
        self.calls = 0

    def _file(self, path: str) -> Path:
        return self.dir / (hashlib.sha1(path.encode()).hexdigest()[:20] + ".json")

    def __contains__(self, path: str) -> bool:
        return True  # the client can always fetch what it lacks

    def get(self, path: str, default=None):
        f = self._file(path)
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))["data"]
            return data if data is not None else default
        if self.offline:
            return default
        data = self._fetch(path)
        f.write_text(json.dumps({"path": path, "data": data}), encoding="utf-8")
        return data if data is not None else default

    def _gh(self, url: str):
        for attempt in range(5):
            self.calls += 1
            out = subprocess.run(
                ["gh", "api", "-H", "Accept: application/vnd.github+json", url],
                capture_output=True,
                timeout=60,
            )
            err = out.stderr.decode("utf-8", "replace")
            if out.returncode == 0:
                return json.loads(out.stdout.decode("utf-8", "replace") or "null")
            if any(f"HTTP {c}" in err for c in ("404", "410", "422", "451")):
                return None
            if "rate limit" in err.lower() or "HTTP 5" in err:
                time.sleep(min(120, 15 * (attempt + 1)))
                continue
            raise GitHubError(f"gh api {url}: {err.strip()[:300]}")
        raise GitHubError(f"gh api {url}: gave up after retries")

    def _fetch(self, path: str):
        if not path.endswith(_LIST_SUFFIXES):
            return self._gh(path)
        items: list = []
        for page in range(1, self.max_pages + 1):
            data = self._gh(f"{path}?per_page=100&page={page}")
            if data is None:
                return None if page == 1 else items
            items.extend(data)
            if len(data) < 100:
                break
        return items
