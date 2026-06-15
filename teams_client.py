"""Microsoft Teams notifier — Funnel Agent / PM agent, Team UW.

Posts Adaptive Cards to a Teams channel via a Power Automate "webhook" workflow
(TEAMS_WEBHOOK_URL). The Workflows trigger accepts a Teams message payload with an
attached Adaptive Card. Degrades gracefully: if the URL is unset or the POST fails,
it returns False instead of raising, so Jira actions never break on a Teams hiccup.
"""
import os

import httpx

WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")
TIMEOUT = 15.0


def configured() -> bool:
    return bool(WEBHOOK_URL)


def text_block(text: str, *, bold=False, color=None, size=None) -> dict:
    el = {"type": "TextBlock", "text": text, "wrap": True}
    if bold:
        el["weight"] = "Bolder"
    if color:           # "Attention" = red, "Good" = green, "Warning" = amber
        el["color"] = color
    if size:            # "Large", "Medium", ...
        el["size"] = size
    return el


def fact_set(facts: list[tuple[str, str]]) -> dict:
    return {"type": "FactSet",
            "facts": [{"title": k, "value": v} for k, v in facts]}


# Full field order shown on a Jira issue panel.
ISSUE_FIELD_ORDER = [
    ("Key", "key"), ("Type", "type"), ("Status", "status"), ("Priority", "priority"),
    ("Assignee", "assignee"), ("Reporter", "reporter"), ("Epic / Parent", "parent"),
    ("Due date", "due"), ("Start date", "start"), ("Labels", "labels"),
    ("Stale after", "stale_after"), ("Created", "created"), ("Updated", "updated"),
]


def issue_card(issue: dict, header: str = "Jira task") -> bool:
    """Post a card with ALL of an issue's fields (never hidden). EMPTY fields are
    shown in red as a 'missing info' nudge; filled fields render normally."""
    body = [text_block(issue.get("summary") or "(no summary)", bold=True)]
    for label, k in ISSUE_FIELD_ORDER:
        v = issue.get(k)
        if isinstance(v, list):
            v = ", ".join(v) if v else None
        if v in (None, ""):
            body.append(text_block(f"{label}: None", bold=True, color="Attention"))
        else:
            body.append(text_block(f"{label}: {v}"))
    desc = issue.get("description")
    first = desc.splitlines()[0].strip() if desc else None  # first line only — keep card compact
    if first:
        body.append(text_block(f"Description: {first}"))
    else:
        body.append(text_block("Description: None", bold=True, color="Attention"))
    return send_card(header, body, url=issue.get("url"))


def digest_card(title: str, issues: list[dict], *, empty_msg: str | None = None,
                accent: str | None = "Attention") -> bool:
    """Post a summary card listing issues (key · summary · owner · due), grouped
    by assignee/owner. If issues is empty, posts empty_msg (or nothing)."""
    if not issues:
        if empty_msg:
            return send_card(title, [text_block(empty_msg, color="Good")])
        return False

    # group by owner/assignee
    groups: dict[str, list[dict]] = {}
    for it in issues:
        who = it.get("owner") or it.get("assignee") or "Unassigned"
        groups.setdefault(who, []).append(it)

    body = [text_block(f"{len(issues)} task(s) — grouped by owner", color=accent)]
    for who, items in groups.items():
        body.append(text_block(f"👤 {who} ({len(items)})", bold=True))
        for it in items:
            due = it.get("due") or "no due date"
            key, url = it.get("key"), it.get("url")
            # Adaptive Card TextBlocks render markdown links -> clickable Jira key
            key_md = f"[{key}]({url})" if url else f"[{key}]"
            extra = ""
            if it.get("idle_days") is not None:
                extra = f" · idle {it['idle_days']}d (limit {it.get('stale_threshold')}d)"
            body.append(text_block(
                f"• {key_md} {it.get('summary')} — {it.get('status')} · due {due}{extra}"))
    return send_card(title, body)


def change_card(issue: dict, changes: list[dict], header: str = "Task updated") -> bool:
    """Post a card for an edited issue: a red 'What changed' section (field,
    old -> new) followed by the FULL current field set. `changes` is a list of
    {field, old, new}."""
    changed = {ch["field"]: ch for ch in changes}  # by field label
    body = [text_block(issue.get("summary") or "(no summary)", bold=True)]
    for label, k in ISSUE_FIELD_ORDER:
        if label in changed:
            ch = changed[label]
            old = ch.get("old") or "None"
            new = ch.get("new") or "None"
            # changed row in red, old -> new
            body.append(text_block(f"{label}: {old}  →  {new}", bold=True, color="Attention"))
        else:
            v = issue.get(k)
            if isinstance(v, list):
                v = ", ".join(v) if v else None
            body.append(text_block(f"{label}: {v if v not in (None, '') else 'None'}"))
    # changed fields not in the standard list (e.g. Sprint, Story points)
    shown = {label for label, _ in ISSUE_FIELD_ORDER}
    for label, ch in changed.items():
        if label not in shown:
            old = ch.get("old") or "None"
            new = ch.get("new") or "None"
            body.append(text_block(f"{label}: {old}  →  {new}", bold=True, color="Attention"))
    return send_card(f"{header} — {issue.get('key')}", body, url=issue.get("url"))


def send_card(title: str, body_elements: list[dict], url: str | None = None) -> bool:
    """Send an Adaptive Card. body_elements is a list of card elements
    (use text_block / fact_set). url adds an 'Open in Jira' action button."""
    if not configured():
        return False
    elements = [text_block(title, bold=True, size="Large")] + body_elements
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": elements,
    }
    if url:
        card["actions"] = [{"type": "Action.OpenUrl", "title": "Open in Jira", "url": url}]
    # The Power Automate flow's "Post card" action is bound to triggerBody(),
    # so we POST the raw Adaptive Card object directly (no message wrapper).
    try:
        r = httpx.post(WEBHOOK_URL, json=card, timeout=TIMEOUT)
        return r.status_code < 300
    except Exception:  # noqa: BLE001 — never break the caller on a Teams error
        return False
