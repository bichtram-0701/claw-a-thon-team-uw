"""Jira Cloud REST client — Sprint Sidekick, Team UW.

Reads the team's (synthetic) project via the v3 API with a personal API token.
Uses /rest/api/3/search/jql (the old /search endpoint was retired).
Note: Jira timestamps can't be backdated, so "stuck" detection uses labels,
status and due dates rather than updated-age.
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


def _brief(issue: dict) -> dict:
    f = issue.get("fields", {})
    return {
        "key": issue.get("key"),
        "summary": f.get("summary"),
        "status": (f.get("status") or {}).get("name"),
        "assignee": ((f.get("assignee") or {}).get("displayName")) or "Unassigned",
        "priority": (f.get("priority") or {}).get("name"),
        "due": f.get("duedate"),
        "labels": f.get("labels") or [],
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


def my_open_issues() -> list[dict]:
    return search(
        "assignee = currentUser() AND statusCategory != Done "
        "ORDER BY due ASC, priority DESC"
    )


def all_open_issues() -> list[dict]:
    return search("statusCategory != Done ORDER BY status, priority DESC", limit=100)


def done_issues() -> list[dict]:
    return search("statusCategory = Done ORDER BY updated DESC", limit=100)


def blocked_issues() -> list[dict]:
    return search(
        'statusCategory != Done AND (labels = "blocked" OR status = "Blocked") '
        "ORDER BY priority DESC"
    )


def overdue_issues() -> list[dict]:
    return search("duedate < now() AND statusCategory != Done ORDER BY due ASC")
