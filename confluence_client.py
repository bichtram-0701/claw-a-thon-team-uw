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


def _inline_markdown(text: str) -> str:
    """Escape text, then render a tiny inline Markdown subset safely."""
    out = html.escape(text or "")
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", out)
    return out


def _split_table_row(line: str) -> list[str]:
    parts = line.strip().strip("|").split("|")
    return [p.strip() for p in parts]


def _is_table_sep(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def _render_table(lines: list[str]) -> str:
    rows = [_split_table_row(x) for x in lines if x.strip().startswith("|")]
    if not rows:
        return ""
    header = rows[0]
    body = rows[2:] if len(rows) > 1 and _is_table_sep(lines[1]) else rows[1:]
    out = ["<table><tbody>"]
    out.append("<tr>" + "".join(f"<th>{_inline_markdown(c)}</th>" for c in header) + "</tr>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{_inline_markdown(c)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)



def _inline_markdown_to_storage(text: str) -> str:
    """Escape text and render a tiny markdown inline subset for Confluence.

    The previous converter escaped the whole line, so Confluence showed literals
    like **Owner:** instead of bold text. Keep this deliberately small and safe:
    bold, italic, inline code, and markdown links.
    """
    safe = html.escape(str(text or ""))

    def link_repl(m: re.Match) -> str:
        label = m.group(1)
        url = m.group(2)
        return f'<a href="{url}">{label}</a>'

    safe = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", link_repl, safe)
    safe = re.sub(r"`([^`]+)`", r"<code>\1</code>", safe)
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", safe)
    safe = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", safe)
    safe = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"<em>\1</em>", safe)
    return safe


def _split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def _table_to_storage(lines: list[str]) -> str:
    rows = [_split_table_row(x) for x in lines if x.strip()]
    if not rows:
        return ""
    has_header = len(rows) >= 2 and _is_table_separator(lines[1])
    header = rows[0] if has_header else []
    body = rows[2:] if has_header else rows
    out = ["<table>"]
    if header:
        out.append("<thead><tr>" + "".join(f"<th>{_inline_markdown_to_storage(c)}</th>" for c in header) + "</tr></thead>")
    out.append("<tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{_inline_markdown_to_storage(c)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def markdown_to_storage(markdown: str) -> str:
    """Convert a safe markdown subset into Confluence storage XHTML.

    Supported because they appear in Watchtower meeting notes:
    - headings (# through ####)
    - unordered bullets using '-' or '*'
    - ordered bullets such as '1.'
    - paragraphs with bold/italic/inline-code/links
    - markdown tables
    - fenced code blocks

    Unsupported markdown is escaped as text instead of passed through raw.
    """
    blocks: list[str] = []
    list_mode: str | None = None
    in_pre = False
    pre_lines: list[str] = []
    lines = str(markdown or "").splitlines()
    i = 0

    def close_list() -> None:
        nonlocal list_mode
        if list_mode:
            blocks.append(f"</{list_mode}>")
            list_mode = None

    def open_list(mode: str) -> None:
        nonlocal list_mode
        if list_mode != mode:
            close_list()
            blocks.append(f"<{mode}>")
            list_mode = mode

    def close_pre() -> None:
        nonlocal in_pre, pre_lines
        if in_pre:
            blocks.append("<pre>" + html.escape("\n".join(pre_lines)) + "</pre>")
            in_pre = False
            pre_lines = []

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_pre:
                close_pre()
            else:
                close_list()
                in_pre = True
                pre_lines = []
            i += 1
            continue
        if in_pre:
            pre_lines.append(line)
            i += 1
            continue
        if not stripped:
            close_list()
            i += 1
            continue

        if stripped.startswith("|"):
            close_list()
            table_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            blocks.append(_table_to_storage(table_lines) or "<pre>" + html.escape("\n".join(table_lines)) + "</pre>")
            continue

        m_head = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if m_head:
            close_list()
            level = len(m_head.group(1))
            blocks.append(f"<h{level}>{_inline_markdown_to_storage(m_head.group(2))}</h{level}>")
            i += 1
            continue

        m_ul = re.match(r"^[-*]\s+(.+)$", stripped)
        if m_ul:
            open_list("ul")
            blocks.append(f"<li>{_inline_markdown_to_storage(m_ul.group(1))}</li>")
            i += 1
            continue

        m_ol = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if m_ol:
            open_list("ol")
            blocks.append(f"<li>{_inline_markdown_to_storage(m_ol.group(1))}</li>")
            i += 1
            continue

        if stripped.startswith(">"):
            close_list()
            blocks.append(f"<blockquote><p>{_inline_markdown_to_storage(stripped.lstrip('> ').strip())}</p></blockquote>")
            i += 1
            continue

        close_list()
        blocks.append(f"<p>{_inline_markdown_to_storage(stripped)}</p>")
        i += 1

    close_pre()
    close_list()
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
