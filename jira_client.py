"""Jira Cloud REST client — Funnel Watchtower, Team UW.

Reads the team's (synthetic) lending-funnel project via the v3 API with a
personal API token. Uses /rest/api/3/search/jql (the old /search was retired).
Each initiative carries an `owner-<name>` label (the free workspace has one
real user, so ownership is encoded in labels) and a `stage-<funnel stage>`
label. Priority encodes criticality; a past due date on an open item = off track.
"""
import os

import httpx

SITE = os.environ.get("ATLASSIAN_SITE", "").rstrip("/")
EMAIL = os.environ.get("ATLASSIAN_EMAIL", "")
TOKEN = os.environ.get("ATLASSIAN_TOKEN", "")
TIMEOUT = 15.0

FIELDS = "summary,status,assignee,priority,duedate,labels,issuetype,updated"


def configured() -> bool:
    return bool(SITE and EMAIL and TOKEN)


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, auth=(EMAIL, TOKEN))


CRITICAL_PRIORITIES = {"highest", "high"}


def _owner_from_labels(labels: list[str]) -> str | None:
    for l in labels:
        if l.lower().startswith("owner-"):
            return l.split("-", 1)[1].replace("_", " ").title()
    return None


def _stage_from_labels(labels: list[str]) -> str | None:
    for l in labels:
        if l.lower().startswith("stage-"):
            return l.split("-", 1)[1].lower()
    return None


def _brief(issue: dict) -> dict:
    f = issue.get("fields", {})
    labels = f.get("labels") or []
    assignee = ((f.get("assignee") or {}).get("displayName")) or "Unassigned"
    return {
        "key": issue.get("key"),
        "summary": f.get("summary"),
        "status": (f.get("status") or {}).get("name"),
        "assignee": assignee,
        "owner": _owner_from_labels(labels) or assignee,
        "stage": _stage_from_labels(labels),
        "priority": (f.get("priority") or {}).get("name"),
        "due": f.get("duedate"),
        "labels": labels,
        "type": (f.get("issuetype") or {}).get("name"),
    }


def search(jql: str, limit: int = 50) -> list[dict]:
    """Run a JQL query, return brief issue dicts."""
    with _client() as c:
        r = c.get(
            f"{SITE}/rest/api/3/search/jql",
            params={"jql": jql, "maxResults": limit, "fields": FIELDS},
        )
        r.raise_for_status()
        return [_brief(i) for i in r.json().get("issues", [])]


# The demo "me" is the lead contributor Rino; their initiatives carry owner-rino.
ME_OWNER_LABEL = os.environ.get("ME_OWNER_LABEL", "owner-rino")


def my_open_issues() -> list[dict]:
    return search(
        f'labels = "{ME_OWNER_LABEL}" AND statusCategory != Done '
        "ORDER BY due ASC, priority DESC"
    )


def all_open_issues() -> list[dict]:
    return search("statusCategory != Done ORDER BY priority DESC, due ASC", limit=100)


def critical_open_issues() -> list[dict]:
    """High/Highest priority initiatives that are still open."""
    return search(
        'statusCategory != Done AND priority in (Highest, High) '
        "ORDER BY due ASC, priority DESC",
        limit=100,
    )


def done_issues() -> list[dict]:
    return search("statusCategory = Done ORDER BY updated DESC", limit=100)


def blocked_issues() -> list[dict]:
    return search(
        'statusCategory != Done AND (labels = "blocked" OR status = "Blocked") '
        "ORDER BY priority DESC"
    )


def overdue_issues() -> list[dict]:
    return search("duedate < now() AND statusCategory != Done ORDER BY due ASC")
