"""Confluence Cloud REST client — Sprint Sidekick, Team UW.

Searches the team's (synthetic) space with CQL and fetches page bodies (v2 API).
"""
import os
import re

import httpx

SITE = os.environ.get("ATLASSIAN_SITE", "").rstrip("/")
EMAIL = os.environ.get("ATLASSIAN_EMAIL", "")
TOKEN = os.environ.get("ATLASSIAN_TOKEN", "")
TIMEOUT = 15.0
MAX_BODY_CHARS = 2500


def configured() -> bool:
    return bool(SITE and EMAIL and TOKEN)


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, auth=(EMAIL, TOKEN))


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def search_pages(query: str, limit: int = 3) -> list[dict]:
    """CQL text search; returns pages with plain-text excerpts and links."""
    cql = f'type = page AND text ~ "{query}"'
    with _client() as c:
        r = c.get(f"{SITE}/wiki/rest/api/search", params={"cql": cql, "limit": limit})
        r.raise_for_status()
        out = []
        for hit in r.json().get("results", []):
            content = hit.get("content") or {}
            page_id = content.get("id")
            body = ""
            if page_id:
                pr = c.get(
                    f"{SITE}/wiki/api/v2/pages/{page_id}",
                    params={"body-format": "storage"},
                )
                if pr.status_code == 200:
                    raw = ((pr.json().get("body") or {}).get("storage") or {}).get("value", "")
                    body = _strip_html(raw)[:MAX_BODY_CHARS]
            out.append({
                "title": content.get("title") or hit.get("title"),
                "url": SITE + "/wiki" + (hit.get("url") or ""),
                "excerpt": _strip_html(hit.get("excerpt") or ""),
                "body": body,
            })
        return out


def recent_pages(limit: int = 10) -> list[dict]:
    with _client() as c:
        r = c.get(f"{SITE}/wiki/api/v2/pages",
                  params={"limit": limit, "sort": "-modified-date"})
        r.raise_for_status()
        return [{"title": p.get("title"), "id": p.get("id")}
                for p in r.json().get("results", [])]
