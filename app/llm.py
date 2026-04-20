from __future__ import annotations

import httpx


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_s: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    async def generate(self, system: str, prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "system": system,
            "prompt": prompt,
            "options": {"temperature": 0.1},
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", "")).strip()
