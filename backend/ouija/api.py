"""HTTP API and static files.

Live séance, in three calls, so the server never needs a GitHub token:

1. POST /api/walk     clone (under the size cap), walk the line, say which GitHub API paths are wanted
2. POST /api/plan     given what the browser fetched so far, say what else is wanted (PRs, then issues)
3. POST /api/seance   build sources from the browser's GitHub JSON, ask the medium, check the quotes

The gallery (precomputed séances from the evaluation) needs none of this.
"""

from __future__ import annotations

import json
import uuid
from collections import OrderedDict
from pathlib import Path
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import clones, gitwalk, seance
from .config import Settings, get_settings
from .ollama import ChatJSON, OllamaClient
from .ratelimit import RateLimiter, limit

MAX_GITHUB_PATHS = 80


class WalkIn(BaseModel):
    owner: str = Field(max_length=100)
    repo: str = Field(max_length=100)
    ref: str = Field(max_length=200)
    path: str = Field(max_length=500)
    line: int = Field(ge=1, le=1_000_000)
    size_kb: int | None = None


class GithubIn(BaseModel):
    walk_id: str
    github: dict = Field(default_factory=dict)


class _Walks:
    """The last few hundred walks, so /plan and /seance need not walk again."""

    def __init__(self, keep: int = 200) -> None:
        self.keep = keep
        self._d: OrderedDict[str, dict] = OrderedDict()
        self._lock = Lock()

    def put(self, w: dict) -> str:
        wid = uuid.uuid4().hex
        with self._lock:
            self._d[wid] = w
            while len(self._d) > self.keep:
                self._d.popitem(last=False)
        return wid

    def get(self, wid: str) -> dict:
        with self._lock:
            w = self._d.get(wid)
        if w is None:
            raise HTTPException(404, "That séance has faded. Start again.")
        return w


def create_app(settings: Settings | None = None, llm: ChatJSON | None = None) -> FastAPI:
    s = settings or get_settings()
    model = llm or OllamaClient(
        s.ollama_base,
        s.model,
        timeout_s=s.llm_timeout_s,
        num_predict=s.llm_num_predict,
        num_thread=s.llm_num_thread,
        num_ctx=s.llm_num_ctx,
    )
    walks = _Walks()
    limiter = RateLimiter(s.rate_per_minute)
    app = FastAPI(title="Ouija Blame", docs_url=None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins.split(","), allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "model": s.model}

    @app.get("/api/gallery")
    def gallery() -> list:
        index = Path(s.gallery_dir) / "index.json"
        return json.loads(index.read_text(encoding="utf-8")) if index.exists() else []

    @app.post("/api/walk", dependencies=[Depends(limit(limiter))])
    def walk(body: WalkIn) -> dict:
        try:
            repo_dir = clones.ensure(
                s.clone_dir, body.owner, body.repo, body.ref, body.size_kb, s.clone_cap_kb, s.clone_keep, s.git_timeout_s
            )
            sha = clones.resolve(repo_dir, body.ref)
            line_text = gitwalk.line_at(repo_dir, sha, body.path, body.line)
            commits = gitwalk.walk(repo_dir, sha, body.path, body.line, timeout=s.git_timeout_s)
        except clones.CloneRefused as e:
            raise HTTPException(413, str(e)) from e
        except gitwalk.GitError as e:
            raise HTTPException(422, f"git could not walk that line: {e}") from e
        if not commits:
            raise HTTPException(422, "No commit touched that line.")
        try:
            seen = gitwalk.last_seen(repo_dir, sha, commits[-1].email)
        except gitwalk.GitError:
            seen = None
        w = {
            "owner": body.owner,
            "repo": body.repo,
            "path": body.path,
            "line": body.line,
            "sha": sha,
            "line_text": line_text,
            "commits": commits,
            "last_seen": seen,
        }
        wid = walks.put(w)
        return {
            "walk_id": wid,
            "line_text": line_text,
            "commits": [{"sha": c.sha, "author": c.author, "date": c.authored, "subject": c.subject} for c in commits],
            "need": seance.plan(commits, {}, body.owner, body.repo),
        }

    def _github(body: GithubIn) -> dict:
        if len(body.github) > MAX_GITHUB_PATHS:
            raise HTTPException(413, "Too many GitHub responses.")
        return body.github

    @app.post("/api/plan")
    def plan(body: GithubIn) -> dict:
        w = walks.get(body.walk_id)
        return {"need": seance.plan(w["commits"], _github(body), w["owner"], w["repo"])}

    @app.post("/api/seance", dependencies=[Depends(limit(limiter))])
    def run(body: GithubIn) -> dict:
        w = walks.get(body.walk_id)
        return seance.run(
            owner=w["owner"],
            repo=w["repo"],
            path=w["path"],
            line=w["line"],
            line_text=w["line_text"],
            commits=w["commits"],
            github=_github(body),
            llm=model,
            last_seen=w["last_seen"],
            passages_shown=s.passages_shown,
            passages_chosen=s.passages_chosen,
        )

    static = Path(s.static_dir)
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="app")
    return app


def app_factory() -> FastAPI:
    return create_app()
