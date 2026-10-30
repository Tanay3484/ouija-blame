"""Shared fixtures: a tiny git repo built in the test, and a fake model. No network anywhere."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _git(repo: Path, *args: str, env_date: str | None = None) -> str:
    env = None
    if env_date:
        import os

        env = {**os.environ, "GIT_AUTHOR_DATE": env_date, "GIT_COMMITTER_DATE": env_date}
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    return out.stdout


@pytest.fixture
def haunted_repo(tmp_path: Path) -> tuple[str, dict]:
    """A repo where line 2 of app.py was written by Ada with a reason, reformatted by Bob, then deleted
    and restored by a revert."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "core.autocrlf", "false")
    f = repo / "app.py"
    shas = {}

    def commit(name: str, email: str, msg: str, text: str, date: str) -> str:
        f.write_text(text, encoding="utf-8", newline="\n")
        _git(repo, "add", "app.py")
        _git(
            repo,
            "-c",
            f"user.name={name}",
            "-c",
            f"user.email={email}",
            "commit",
            "-q",
            "-m",
            msg,
            env_date=date,
        )
        return _git(repo, "rev-parse", "HEAD").strip()

    shas["origin"] = commit(
        "Ada",
        "1+ada@users.noreply.github.com",
        "Retry the socket once (#12)\n\nThe proxy drops the first packet after idle, so we retry once.",
        "def send(s):\n    s.retry(1)\n    return s\n",
        "2019-03-01T10:00:00+00:00",
    )
    shas["format"] = commit(
        "Bob",
        "bob@example.com",
        "Reformat with black (#40)",
        "def send(s):\n    s.retry( 1 )\n    return s\n",
        "2021-06-01T10:00:00+00:00",
    )
    shas["deletion"] = commit(
        "Cy",
        "cy@example.com",
        "Remove pointless retry (#77)",
        "def send(s):\n    return s\n",
        "2024-01-01T10:00:00+00:00",
    )
    shas["revert"] = commit(
        "Cy",
        "cy@example.com",
        f'Revert "Remove pointless retry (#77)"\n\nThis reverts commit {shas["deletion"]}.',
        "def send(s):\n    s.retry( 1 )\n    return s\n",
        "2024-01-02T10:00:00+00:00",
    )
    return str(repo), shas


class FakeLLM:
    def __init__(self, reply: dict | Exception):
        self.reply = reply
        self.calls: list[dict] = []

    def chat_json(self, messages, schema, temperature=0.6):
        self.calls.append({"messages": messages, "schema": schema})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture
def fake_llm():
    return FakeLLM
