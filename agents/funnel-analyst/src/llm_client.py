"""
OpenAI-compatible client for GreenNode MaaS (Gemma / Qwen).

GreenNode MaaS exposes an OpenAI-compatible API, so we POST to
{base_url}/chat/completions with a Bearer key. All settings are read from env so
the same code targets the public MaaS endpoint or a self-hosted OpenClaw
instance URL (both provided in the Claw-a-thon welcome email).

Env vars:
    LLM_BASE_URL   e.g. https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
    LLM_API_KEY    your GreenNode MaaS API key  (or GREENNODE_API_KEY)
    LLM_MODEL      e.g. gemma-4-31b-it  or  Qwen-3-27B

If no key is configured the client reports unavailable, and the agent falls back
to a deterministic template report so demos never break.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


class LLMClient:
    def __init__(self,
                 base_url: str | None = None,
                 api_key: str | None = None,
                 model: str | None = None,
                 timeout: int = 60):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL")
                         or "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1").rstrip("/")
        self.api_key = (api_key or os.getenv("LLM_API_KEY")
                        or os.getenv("GREENNODE_API_KEY") or "")
        self.model = model or os.getenv("LLM_MODEL") or "gemma-4-31b-it"
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str,
             temperature: float = 0.3, max_tokens: int = 1200) -> str:
        if not self.available:
            raise RuntimeError(
                "No LLM_API_KEY / GREENNODE_API_KEY set — cannot call MaaS.")
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")[:300]
            raise RuntimeError(f"MaaS HTTP {e.code}: {body}")
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"MaaS request failed: {e}")
        return data["choices"][0]["message"]["content"].strip()
# end of file
