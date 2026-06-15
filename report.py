"""LLM helpers for Funnel Agent.

The configured LLM is used as a controlled language layer: semantic routing, bounded
field extraction and narration from verified JSON. Business metrics, rankings,
SQL safety and write decisions live in deterministic code.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

_MODEL_CACHE: dict[str, str] = {}
_MODEL_OVERRIDE: str | None = None


PREFERRED_GPT_OSS_20B_MODEL_ID = "openai/gpt-oss-20b"


def _client():
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")
    model = os.environ.get("LLM_MODEL") or _MODEL_CACHE.get("name")
    if not (api_key and base_url):
        return None, None
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=float(os.environ.get("LLM_TIMEOUT", "25")))
    if not model:
        try:
            model = _discover_model(client)
            if model:
                _MODEL_CACHE["name"] = model
        except Exception as e:  # noqa: BLE001
            print(f"Model discovery failed ({e})")
            return None, None
    return (client, model) if model else (None, None)


def _discover_model(client) -> str | None:
    """Ask the serving endpoint for model ids; prefer GPT-OSS 20B for the chat layer.

    Business facts still come from deterministic code. GPT-OSS is used for
    language, field extraction, and bounded narration.
    """
    models = client.models.list()
    ids = [m.id for m in getattr(models, "data", models)]
    lower = {i.lower(): i for i in ids}
    preferred_exact = os.environ.get("LLM_PREFERRED_MODEL") or PREFERRED_GPT_OSS_20B_MODEL_ID
    if preferred_exact in ids:
        return preferred_exact
    # Older packages used the md-* id for GPT-OSS 20B. Keep it as a fallback if the
    # serving endpoint exposes model ids that way.
    legacy_id = "md-7c838436-12d0-4174-ad8b-ad324d85a6b9"
    if legacy_id in ids:
        return legacy_id
    # Some MaaS deployments expose readable ids; others expose md-* ids. Prefer
    # GPT-OSS when available, then fall back to previous contest defaults.
    return (next((i for i in ids if "gpt-oss-20b" in i.lower()), None)
            or next((i for i in ids if "gpt-oss" in i.lower() and "20" in i.lower()), None)
            or next((i for i in ids if "gpt" in i.lower()), None)
            or next((i for i in ids if "qwen" in i.lower()), None)
            or next((i for i in ids if "gemma" in i.lower()), None)
            or (ids[0] if ids else None))


def _profile_defaults(profile: str | None, temperature: float, max_tokens: int, enable_thinking: bool) -> tuple[float, int, bool]:
    if profile in {"classifier", "extract", "json"}:
        return 0.0, min(max_tokens, 500), False
    if profile == "reasoning":
        # Keep reasoning bounded; turn thinking on only when explicitly enabled.
        thinking = enable_thinking or os.environ.get("LLM_ENABLE_THINKING", "false").lower() in ("1", "true", "yes")
        return min(temperature, 0.2), max_tokens, thinking
    return temperature, max_tokens, enable_thinking


def _call(client, model: str, system: str, user: str, max_tokens: int,
          temperature: float, enable_thinking: bool, *, with_extra_body: bool = True) -> str | None:
    kwargs = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if with_extra_body:
        # Some MaaS servers use this to disable verbose thinking output.
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": bool(enable_thinking)}}
    resp = client.chat.completions.create(**kwargs)
    content = (resp.choices[0].message.content or "").strip()
    return content or None


def llm_chat(system: str, user: str, max_tokens: int = 900,
             temperature: float = 0.2, enable_thinking: bool = False,
             profile: str | None = None) -> str | None:
    """One robust LLM call; returns None on failure so callers can fall back."""
    global _MODEL_OVERRIDE
    temperature, max_tokens, enable_thinking = _profile_defaults(profile, temperature, max_tokens, enable_thinking)
    client, model = _client()
    if client is None or model is None:
        return None
    model = _MODEL_OVERRIDE or model

    attempts: list[tuple[str, bool]] = [(model, True)]
    # Some OpenAI-compatible servers reject extra_body. Retry without it.
    attempts.append((model, False))

    last_error: Exception | None = None
    for model_name, with_extra in attempts:
        try:
            return _call(client, model_name, system, user, max_tokens, temperature, enable_thinking, with_extra_body=with_extra)
        except Exception as e:  # noqa: BLE001
            last_error = e
            text = str(e).lower()
            if not with_extra and ("not found" in text or "404" in text):
                try:
                    pick = _discover_model(client)
                    if pick and pick != model_name:
                        print(f"Model '{model_name}' not found; switching to '{pick}'")
                        _MODEL_OVERRIDE = pick
                        try:
                            return _call(client, pick, system, user, max_tokens, temperature, enable_thinking, with_extra_body=True)
                        except Exception:
                            return _call(client, pick, system, user, max_tokens, temperature, enable_thinking, with_extra_body=False)
                except Exception as e2:  # noqa: BLE001
                    print(f"Model autodiscovery failed ({e2})")
            # On first extra_body-related failure, immediately try the same model without it.
            if with_extra and any(s in text for s in ("extra_body", "chat_template", "unknown field", "unexpected")):
                continue
    print(f"LLM call failed ({last_error}); falling back")
    return None


def extract_json(text: str | None) -> dict | None:
    """Best-effort JSON object extraction from small-model output."""
    if not text:
        return None
    s = text.strip()
    s = re.sub(r"^```(?:json)?", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"```$", "", s).strip()
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        s = s[start:end + 1]
    try:
        data = json.loads(s)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def llm_json(system: str, user: str, max_tokens: int = 400, temperature: float = 0.0, **_ignored) -> dict | None:
    raw = llm_chat(system + "\nReturn ONLY a valid JSON object. No prose, no code fences.",
                   user, max_tokens=max_tokens, temperature=temperature, profile="json")
    return extract_json(raw)


def narrate_json(question: str, result: dict[str, Any], *, system_extra: str = "",
                 lang: str = "en", max_tokens: int = 900) -> str | None:
    lang_line = "Answer in Vietnamese." if lang == "vi" else "Answer in the user's language, default English."
    return llm_chat(
        "You are Funnel Agent, a business-funnel execution intelligence assistant. "
        "Use ONLY the JSON data provided. Never invent issue keys, owners, values, page titles, URLs, causes, or decisions. "
        "Start with the direct answer. For broad status requests, use concise markdown. "
        "For diagnostics, say 'concentrated in' rather than 'caused by' unless the JSON explicitly proves causality. "
        + system_extra + " " + lang_line,
        "Question: " + question + "\nData JSON:\n" + json.dumps(result, ensure_ascii=False),
        max_tokens=max_tokens,
        temperature=0.2,
    )


# Compatibility aliases used by current app/tests.
def extract_json_object(text: str | None) -> dict | None:
    return extract_json(text)


def narrate_from_json(system: str, question: str, result: dict, *, lang: str = "en", max_tokens: int = 900) -> str | None:
    return narrate_json(question, result, system_extra=system, lang=lang, max_tokens=max_tokens)


def one_line(text: str | None) -> str | None:
    if not text:
        return None
    return text.strip().splitlines()[0].strip().strip("`.,!\"'") or None


def model_label() -> str:
    """Human-readable configured model label for /version and /model."""
    return (_MODEL_OVERRIDE
            or os.environ.get("LLM_MODEL")
            or _MODEL_CACHE.get("name")
            or os.environ.get("LLM_PREFERRED_MODEL")
            or PREFERRED_GPT_OSS_20B_MODEL_ID)


def model_info() -> dict:
    """Safe runtime model metadata. Does not expose API keys or secrets."""
    configured = os.environ.get("LLM_MODEL")
    source = "LLM_MODEL env" if configured else "preferred/default"
    model = model_label()
    if _MODEL_OVERRIDE and _MODEL_OVERRIDE != configured:
        source = "runtime autodiscovery/override"
        model = _MODEL_OVERRIDE
    return {
        "model": model,
        "configured_model": configured or None,
        "preferred_model": os.environ.get("LLM_PREFERRED_MODEL") or PREFERRED_GPT_OSS_20B_MODEL_ID,
        "source": source,
        "llm_configured": bool(os.environ.get("LLM_API_KEY") and os.environ.get("LLM_BASE_URL")),
        "note": "Model identity comes from Funnel Agent runtime config, not from model self-reporting.",
    }
