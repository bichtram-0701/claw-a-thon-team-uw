"""Confluence Cloud client for Funnel Watchtower.

Reads decision pages and can publish weekly meeting summaries. The caller owns
write gating (ALLOW_WRITES); this module only performs configured REST calls.
"""
from __future__ import annotations

from datetime import date
import html
import os
import re
from typing import Any

import httpx

SITE = os.environ.get("ATLASSIAN_SITE", "").rstrip("/")
EMAIL = os.environ.get("ATLASSIAN_EMAIL", "")
TOKEN = os.environ.get("ATLASSIAN_TOKEN", "")
TIMEOUT = 15.0
MAX_BODY_CHARS = 3000


def configured() -> bool:
    return bool(SITE and EMAIL and TOKEN)


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, auth=(EMAIL, TOKEN))


def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _escape_cql(s: str) -> str:
    return str(s or "").replace('"', '\\"')[:200]


def _page_url(page_id: str | None) -> str | None:
    return SITE + "/wiki/spaces/~/pages/" + str(page_id) if page_id else None


def _fetch_body(c: httpx.Client, page_id: str | None) -> str:
    if not page_id:
        return ""
    r = c.get(f"{SITE}/wiki/api/v2/pages/{page_id}", params={"body-format": "storage"})
    if r.status_code != 200:
        return ""
    raw = ((r.json().get("body") or {}).get("storage") or {}).get("value", "")
    return _strip_html(raw)[:MAX_BODY_CHARS]


def search_pages(query: str, limit: int = 3) -> list[dict[str, Any]]:
    """CQL text search; returns pages with plain-text excerpts and links."""
    if not configured():
        return []
    cql = f'type = page AND text ~ "{_escape_cql(query)}"'
    with _client() as c:
        r = c.get(f"{SITE}/wiki/rest/api/search", params={"cql": cql, "limit": limit})
        r.raise_for_status()
        out = []
        for hit in r.json().get("results", []):
            content = hit.get("content") or {}
            page_id = content.get("id")
            out.append({
                "id": page_id,
                "title": content.get("title") or hit.get("title"),
                "url": SITE + "/wiki" + (hit.get("url") or "") if hit.get("url") else _page_url(page_id),
                "excerpt": _strip_html(hit.get("excerpt") or ""),
                "body": _fetch_body(c, page_id),
            })
        return out


def recent_pages(limit: int = 10, with_body: bool = False, include_body: bool | None = None) -> list[dict[str, Any]]:
    """Return recently modified pages; optionally include plain-text body."""
    if include_body is not None:
        with_body = include_body
    if not configured():
        return []
    with _client() as c:
        r = c.get(f"{SITE}/wiki/api/v2/pages", params={"limit": limit, "sort": "-modified-date"})
        r.raise_for_status()
        pages = []
        for p in r.json().get("results", []):
            page_id = p.get("id")
            item = {"title": p.get("title"), "id": page_id, "url": _page_url(page_id)}
            if with_body:
                item["body"] = _fetch_body(c, page_id)
            pages.append(item)
        return pages


def default_space_id() -> str | None:
    env = os.environ.get("CONFLUENCE_SPACE_ID")
    if env:
        return env
    if not configured():
        return None
    wanted_key = os.environ.get("CONFLUENCE_SPACE_KEY")
    with _client() as c:
        r = c.get(f"{SITE}/wiki/api/v2/spaces", params={"limit": 50})
        if r.status_code != 200:
            return None
        spaces = [s for s in r.json().get("results", []) if s.get("type") != "personal"]
        if wanted_key:
            for s in spaces:
                if s.get("key") == wanted_key:
                    return s.get("id")
        return spaces[0].get("id") if spaces else None


def markdown_to_storage(markdown: str) -> str:
    """Small, safe markdown subset for Confluence storage format.

    We intentionally keep this conservative: headings, bullets and paragraphs.
    Tables/code are preserved as preformatted text so meeting notes remain readable
    even when the LLM emits markdown tables.
    """
    blocks: list[str] = []
    in_ul = False
    in_pre = False
    pre_lines: list[str] = []

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            blocks.append("</ul>")
            in_ul = False

    def close_pre() -> None:
        nonlocal in_pre, pre_lines
        if in_pre:
            blocks.append("<pre>" + html.escape("\n".join(pre_lines)) + "</pre>")
            in_pre = False
            pre_lines = []

    for raw in str(markdown or "").splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if in_pre:
                close_pre()
            else:
                close_ul()
                in_pre = True
                pre_lines = []
            continue
        if in_pre:
            pre_lines.append(line)
            continue
        if not line:
            close_ul()
            continue
        if line.startswith("# "):
            close_ul(); blocks.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            close_ul(); blocks.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            close_ul(); blocks.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_ul:
                blocks.append("<ul>"); in_ul = True
            blocks.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.startswith("|"):
            close_ul(); blocks.append("<pre>" + html.escape(line) + "</pre>")
        else:
            close_ul(); blocks.append(f"<p>{html.escape(line)}</p>")
    close_pre()
    close_ul()
    return "\n".join(blocks) or "<p>No content.</p>"


def _find_page(title: str, space_id: str | None = None) -> dict[str, Any] | None:
    if not configured():
        return None
    cql = f'type = page AND title = "{_escape_cql(title)}"'
    with _client() as c:
        r = c.get(f"{SITE}/wiki/rest/api/search", params={"cql": cql, "limit": 5})
        if r.status_code != 200:
            return None
        for hit in r.json().get("results", []):
            content = hit.get("content") or {}
            page_id = content.get("id")
            if not page_id:
                continue
            pr = c.get(f"{SITE}/wiki/api/v2/pages/{page_id}")
            if pr.status_code != 200:
                continue
            page = pr.json()
            if space_id and str(page.get("spaceId")) != str(space_id):
                continue
            return {"id": page_id, "title": content.get("title"), "url": _page_url(page_id), "version": page.get("version", {})}
    return None


def create_page(title: str, markdown_body: str) -> dict[str, Any]:
    """Create a Confluence page in the configured/default space."""
    sid = default_space_id()
    if not sid:
        return {"error": "no Confluence space found"}
    payload = {
        "spaceId": sid,
        "status": "current",
        "title": title,
        "body": {"representation": "storage", "value": markdown_to_storage(markdown_body)},
    }
    with _client() as c:
        r = c.post(f"{SITE}/wiki/api/v2/pages", json=payload)
        if r.status_code < 300:
            page = r.json()
            return {"id": page.get("id"), "title": page.get("title"), "url": _page_url(page.get("id")), "created": True}
        return {"error": f"{r.status_code} {r.text[:180]}"}


def upsert_page(title: str, markdown_body: str) -> dict[str, Any]:
    """Update an existing weekly page with the same title, else create it."""
    sid = default_space_id()
    if not sid:
        return {"error": "no Confluence space found"}
    existing = _find_page(title, sid)
    if not existing:
        return create_page(title, markdown_body)
    page_id = existing["id"]
    version_no = int((existing.get("version") or {}).get("number") or 1) + 1
    payload = {
        "id": page_id,
        "status": "current",
        "title": title,
        "spaceId": sid,
        "body": {"representation": "storage", "value": markdown_to_storage(markdown_body)},
        "version": {"number": version_no, "message": "Updated by Funnel Watchtower weekly summary"},
    }
    with _client() as c:
        r = c.put(f"{SITE}/wiki/api/v2/pages/{page_id}", json=payload)
        if r.status_code < 300:
            page = r.json()
            return {"id": page.get("id") or page_id, "title": page.get("title") or title, "url": _page_url(page.get("id") or page_id), "updated": True}
        return {"error": f"{r.status_code} {r.text[:180]}", "id": page_id, "url": _page_url(page_id)}


def weekly_title(as_of: str | None = None) -> str:
    return "Weekly Funnel Watchtower Summary - " + (as_of or date.today().isoformat())
