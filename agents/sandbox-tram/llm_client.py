"""OpenAI-compatible client for GreenNode MaaS (Qwen / Gemma).

GreenNode MaaS exposes an OpenAI-compatible API, so we POST to
{base_url}/chat/completions with a Bearer key. All settings read from env.

Env vars:
    LLM_BASE_URL   e.g. https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
    LLM_API_KEY    your GreenNode MaaS API key  (or GREENNODE_API_KEY)
    LLM_MODEL      e.g. Qwen-3-27B  or  gemma-4-31b-it

If no key is configured the client reports unavailable, and the agent falls back
to a deterministic template so demos never break.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


class LLMClient:
    def __init__(self, base_url=None, api_key=None, model=None, timeout=60):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL")
                         or "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1").rstrip("/")
        self.api_key = (api_key or os.getenv("LLM_API_KEY")
                        or os.getenv("GREENNODE_API_KEY") or "")
        self.model = model or os.getenv("LLM_MODEL") or "qwen/qwen3-5-27b"
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str,
             temperature: float = 0.3, max_tokens: int = 800) -> str:
        if not self.available:
            raise RuntimeError("No LLM_API_KEY / GREENNODE_API_KEY set — cannot call MaaS.")
        url = f"{self.base_url}/chat/completions"
        # Qwen3 models "think" by default and return content=null. Disable it:
        # /no_think marker in the prompt + chat_template_kwargs for vLLM backends.
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system + " /no_think"},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
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
        msg = data["choices"][0]["message"]
        # thinking models may put text in reasoning_content when content is null
        text = msg.get("content") or msg.get("reasoning_content") or ""
        return text.strip()
