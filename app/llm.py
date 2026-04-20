from __future__ import annotations

import httpx


class DisabledLLMClient:
    def generate(self, system: str, prompt: str) -> str:
        del system, prompt
        raise RuntimeError("Live LLM agents are disabled")


class OllamaClient:
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


class PydanticAIClient:
    """PydanticAI adapter for Ollama's OpenAI-compatible chat endpoint."""

    def __init__(self, base_url: str, model: str) -> None:
        try:
            import pydantic_ai  # noqa: F401
        except ImportError as error:
            raise RuntimeError("pydantic-ai is not installed") from error

        self.base_url = self._openai_compatible_url(base_url)
        self.model = model

    def generate(self, system: str, prompt: str) -> str:
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.ollama import OllamaProvider

        ollama_model = OpenAIChatModel(
            model_name=self.model,
            provider=OllamaProvider(base_url=self.base_url),
        )
        agent = Agent(ollama_model, instructions=system)
        result = agent.run_sync(prompt)
        return str(result.output).strip()

    @staticmethod
    def _openai_compatible_url(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            return normalized
        return f"{normalized}/v1"
