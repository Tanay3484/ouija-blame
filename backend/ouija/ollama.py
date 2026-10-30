"""Minimal Ollama chat client with JSON-schema constrained output (https://docs.ollama.com/api).

Adapted from Slow Start (Week 3, same author). Behind `ChatJSON` so tests use a fake.
"""

from __future__ import annotations

import json
from typing import Protocol

import httpx


class LLMError(Exception):
    """Model unreachable, timed out, or returned something that is not a JSON object."""


class ChatJSON(Protocol):
    def chat_json(self, messages: list[dict], schema: dict, temperature: float = 0.6) -> dict: ...


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float = 60,
        num_predict: int = 160,
        num_thread: int | None = None,
        num_ctx: int | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_predict = num_predict
        self.num_thread = num_thread
        self.num_ctx = num_ctx
        self._http = http or httpx.Client(timeout=timeout_s)

    def chat_json(self, messages: list[dict], schema: dict, temperature: float = 0.6) -> dict:
        # num_predict caps runaway output: small models under a schema can loop.
        options: dict = {"temperature": temperature, "num_predict": self.num_predict}
        if self.num_thread:
            options["num_thread"] = self.num_thread
        if self.num_ctx:
            options["num_ctx"] = self.num_ctx
        try:
            resp = self._http.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "format": schema,
                    "stream": False,
                    "options": options,
                },
            )
            resp.raise_for_status()
            data = json.loads(resp.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
            raise LLMError(f"{type(e).__name__}: {e}") from e
        if not isinstance(data, dict):
            raise LLMError("model returned JSON that is not an object")
        return data
