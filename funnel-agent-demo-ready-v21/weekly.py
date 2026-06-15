"""Weekly meeting summary helper.

main.py calls the weekly path directly, but this module is useful for scripts or
manual tests. It builds the same deterministic packet, asks the model only to
write meeting-ready markdown, and optionally publishes to Confluence.
"""
from __future__ import annotations

from datetime import date
import re

import briefing as bf
import confluence_client as cf
import report as rp


def wants_publish(message: str) -> bool:
    msg = (message or "").lower()
    return any(k in msg for k in ["publish", "post", "create page", "write to confluence", "save to confluence", "confluence page"])


def build_pack(message: str = "") -> dict:
    pack = bf.weekly_meeting_pack()
    pack["question"] = message
    return pack


def fallback_markdown(pack: dict) -> str:
    return bf.render_weekly_summary(pack)


def narrate(pack: dict, message: str, lang: str = "en") -> str:
    # Canonical weekly notes are deterministic so Confluence output is stable.
    # The LLM is intentionally not used here because meeting artifacts should not
    # drift across runs or invent/rephrase operational facts.
    return fallback_markdown(pack)


def make_title(markdown: str | None = None, as_of: str | None = None) -> str:
    if markdown:
        m = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
        if m:
            return m.group(1)[:120]
    return cf.weekly_title(as_of or date.today().isoformat())


def handle(message: str, allow_writes: bool, lang: str = "en") -> dict:
    pack = build_pack(message)
    markdown = narrate(pack, message, lang=lang)
    published = None
    if wants_publish(message):
        if not allow_writes:
            published = {"skipped": True, "reason": "ALLOW_WRITES=false"}
        else:
            published = cf.upsert_page(make_title(markdown, pack.get("as_of")), markdown)
    return {"markdown": markdown, "pack": pack, "published": published, "publish_requested": wants_publish(message)}
