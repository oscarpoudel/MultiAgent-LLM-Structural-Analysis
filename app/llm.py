"""LLM clients for the multi-agent system.

Every client exposes two methods:

- ``generate(system, prompt) -> str``: plain text completion.
- ``chat(system, messages, tools, tool_choice) -> LLMReply``: chat completion
  with optional native tool/structured-output calls.

Tool calling is the backbone of the multi-agent system: each specialist agent
asks the model to fill a typed JSON schema (derived from a Pydantic model)
instead of parsing free-form text, which is far more reliable on small local
models.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class LLMReply:
    """Normalized result of a chat completion."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    @property
    def first_tool(self) -> dict[str, Any] | None:
        return self.tool_calls[0] if self.tool_calls else None


def _coerce_arguments(raw: Any) -> dict[str, Any]:
    """Tool arguments may arrive as a dict or a JSON string."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


class DisabledLLMClient:
    """No live LLM. Every call raises so callers fall back gracefully."""

    def generate(self, system: str, prompt: str) -> str:
        del system, prompt
        raise RuntimeError("Live LLM agents are disabled")

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMReply:
        del system, messages, tools, tool_choice
        raise RuntimeError("Live LLM agents are disabled")


class OllamaClient:
    """Ollama native API client (``/api/generate`` + ``/api/chat``)."""

    def __init__(self, base_url: str, model: str, timeout_s: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def generate(self, system: str, prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "system": system,
            "prompt": prompt,
            "options": {"temperature": 0.1},
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data.get("response", "")).strip()

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMReply:
        msgs: list[dict[str, Any]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        # Build candidate payloads from most to least capable. Some Ollama
        # backends reject the `tool_choice` field (400), and others reject
        # `tools` entirely, so we degrade gracefully:
        #   1. tools + tool_choice   2. tools only   3. no tools (JSON-in-text)
        candidates: list[dict[str, Any]] = []
        if tools:
            with_choice = {
                "model": self.model, "messages": msgs, "stream": False,
                "options": {"temperature": 0.1}, "tools": tools, "tool_choice": tool_choice or "auto",
            }
            candidates.append(with_choice)
            candidates.append({k: v for k, v in with_choice.items() if k != "tool_choice"})
        candidates.append({
            "model": self.model, "messages": msgs, "stream": False,
            "options": {"temperature": 0.1},
        })

        last_error: Exception | None = None
        for payload in candidates:
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    response = client.post(f"{self.base_url}/api/chat", json=payload)
                    response.raise_for_status()
                    data = response.json()
                break
            except httpx.HTTPStatusError as error:
                last_error = error
                status = error.response.status_code if error.response is not None else 0
                # 400/422 = the backend rejected this payload shape; try the
                # next (simpler) candidate. Any other error is fatal.
                if status in (400, 422):
                    continue
                raise
        else:
            raise last_error if last_error else RuntimeError("Ollama chat failed")

        message = data.get("message", {}) or {}
        text = str(message.get("content", "") or "").strip()
        tool_calls: list[dict[str, Any]] = []
        for tc in message.get("tool_calls", []) or []:
            fn = tc.get("function", {}) or {}
            tool_calls.append(
                {"name": fn.get("name", ""), "arguments": _coerce_arguments(fn.get("arguments"))}
            )
        return LLMReply(text=text, tool_calls=tool_calls)


class PydanticAIClient:
    """OpenAI-compatible chat client (works with Ollama's ``/v1`` endpoint).

    Kept for the ``pydanticai`` provider value. Uses the OpenAI-compatible
    chat completions endpoint so tool calling behaves identically to the
    native Ollama client.
    """

    def __init__(self, base_url: str, model: str, timeout_s: float = 12.0) -> None:
        self.base_url = self._openai_compatible_url(base_url)
        self.model = model
        self.timeout_s = timeout_s

    def generate(self, system: str, prompt: str) -> str:
        reply = self.chat(system, [{"role": "user", "content": prompt}])
        return reply.text

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMReply:
        msgs: list[dict[str, Any]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "stream": False,
            "temperature": 0.1,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {}) or {}
        text = str(message.get("content", "") or "").strip()
        tool_calls: list[dict[str, Any]] = []
        for tc in message.get("tool_calls", []) or []:
            fn = tc.get("function", {}) or {}
            tool_calls.append(
                {"name": fn.get("name", ""), "arguments": _coerce_arguments(fn.get("arguments"))}
            )
        return LLMReply(text=text, tool_calls=tool_calls)

    @staticmethod
    def _openai_compatible_url(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            return normalized
        return f"{normalized}/v1"
