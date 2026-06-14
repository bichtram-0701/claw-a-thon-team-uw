"""Jira Cloud REST client — Funnel Watchtower, Team UW.

Reads/writes the synthetic business-funnel project via the Jira Cloud v3 API.
Ownership is normalized from real assignee and/or `owner-<name>` labels; funnel
stage is encoded as `stage-<traffic|submission|approval|disbursement|crosscut>`.
Writes are still gated by main.ALLOW_WRITES.
"""
from __future__ import annotations

import os
import re

import httpx

SITE = os.environ.get("ATLASSIAN_SITE", "").rstrip("/")
EMAIL = os.environ.get("ATLASSIAN_EMAIL", "")
TOKEN = os.environ.get("ATLASSIAN_TOKEN", "")
TIMEOUT = 15.0

FIELDS = "summary,status,assignee,duedate,labels,issuetype,updated,created,parent"


def configured() -> bool:
    return bool(SITE and EMAIL and TOKEN)


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, auth=(EMAIL, TOKEN))


def _owner_from_labels(labels: list[str]) -> str | None:
    for l in labels:
        if l.lower().startswith("owner-"):
            return l.split("-", 1)[1].replace("_", " ").replace("-", " ").title()
    return None


def _stage_from_labels(labels: list[str]) -> str | None:
    for l in labels:
        if l.lower().startswith("stage-"):
            return l.split("-", 1)[1].lower()
    return None


def _epic_from_parent(f: dict) -> str | None:
    """The Epic (= funnel stage / project) this task belongs to, from its parent."""
    parent = f.get("parent") or {}
    pf = parent.get("fields") or {}
    if (pf.get("issuetype") or {}).get("name") == "Epic" or parent.get("key"):
        return pf.get("summary") or parent.get("key")
    return None


def _brief(issue: dict) -> dict:
    f = issue.get("fields", {})
    labels = f.get("labels") or []
    assignee = ((f.get("assignee") or {}).get("displayName")) or "Unassigned"
    stage = _stage_from_labels(labels)
    epic = _epic_from_parent(f)
    return {
        "key": issue.get("key"),
        "url": f"{SITE}/browse/{issue.get('key')}",
        "summary": f.get("summary"),
        "status": (f.get("status") or {}).get("name"),
        "assignee": assignee,
        "owner": _owner_from_labels(labels) or assignee,
        "stage": stage,
        "epic": epic or (stage.title() if stage else None),
        "due": f.get("duedate"),
        "created": f.get("created"),
        "updated": f.get("updated"),
        "labels": labels,
        "type": (f.get("issuetype") or {}).get("name"),
    }


FULL_FIELDS = ("summary,status,assignee,reporter,duedate,labels,issuetype,"
               "parent,priority,created,updated,description")


def _adf_text(node) -> str:
    """Flatten an ADF description object to plain text."""
    if not isinstance(node, dict):
        return ""
    out = node.get("text", "")
    for child in node.get("content", []) or []:
        out += _adf_text(child)
        if child.get("type") in ("paragraph", "heading"):
            out += "\n"
    return out


def _adf_doc(text: str | None) -> dict | None:
    """Very small markdown-ish text -> Jira ADF paragraph document."""
    if not text:
        return None
    content = []
    for raw in str(text).splitlines():
        line = raw.rstrip()
        if not line:
            content.append({"type": "paragraph", "content": []})
            continue
        if line.startswith("# "):
            content.append({"type": "heading", "attrs": {"level": 1},
                            "content": [{"type": "text", "text": line[2:]}]})
        elif line.startswith("## "):
            content.append({"type": "heading", "attrs": {"level": 2},
                            "content": [{"type": "text", "text": line[3:]}]})
        else:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": line}]})
    return {"type": "doc", "version": 1, "content": content}


def get_issue_full(key: str) -> dict:
    """All panel fields of one issue, normalized for a Teams card."""
    with _client() as c:
        r = c.get(f"{SITE}/rest/api/3/issue/{key}", params={"fields": FULL_FIELDS})
        r.raise_for_status()
        f = r.json().get("fields", {})
    parent = f.get("parent") or {}
    pf = parent.get("fields") or {}
    return {
        "key": key,
        "url": f"{SITE}/browse/{key}",
        "summary": f.get("summary"),
        "type": (f.get("issuetype") or {}).get("name"),
        "status": (f.get("status") or {}).get("name"),
        "priority": (f.get("priority") or {}).get("name"),
        "assignee": (f.get("assignee") or {}).get("displayName"),
        "reporter": (f.get("reporter") or {}).get("displayName"),
        "parent": (f"{parent.get('key')} ({pf.get('summary')})" if parent.get("key") else None),
        "due": f.get("duedate"),
        "labels": f.get("labels") or [],
        "created": (f.get("created") or "")[:10] or None,
        "updated": (f.get("updated") or "")[:10] or None,
        "description": _adf_text(f.get("description")).strip() or None,
    }


_CHANGELOG_LABEL = {
    "status": "Status", "assignee": "Assignee", "duedate": "Due date",
    "priority": "Priority", "summary": "Summary", "labels": "Labels",
    "reporter": "Reporter", "issuetype": "Type", "parent": "Epic / Parent",
    "Parent": "Epic / Parent", "IssueParentAssociation": "Epic / Parent",
    "description": "Description",
}


def get_latest_changes(key: str) -> list[dict]:
    """The most recent changelog entry for an issue, as [{field, old, new}]."""
    with _client() as c:
        r = c.get(f"{SITE}/rest/api/3/issue/{key}",
                  params={"expand": "changelog", "fields": "summary"})
        r.raise_for_status()
        histories = (r.json().get("changelog") or {}).get("histories") or []
    if not histories:
        return []
    latest = max(histories, key=lambda h: h.get("created", ""))
    out = []
    for it in latest.get("items", []):
        field = it.get("field") or "Field"
        out.append({
            "field": _CHANGELOG_LABEL.get(field, field),
            "old": it.get("fromString"),
            "new": it.get("toString"),
        })
    return out


def search(jql: str, limit: int = 50) -> list[dict]:
    """Run a JQL query, return brief issue dicts."""
    with _client() as c:
        r = c.get(
            f"{SITE}/rest/api/3/search/jql",
            params={"jql": jql, "maxResults": limit, "fields": FIELDS},
        )
        r.raise_for_status()
        return [_brief(i) for i in r.json().get("issues", [])]


ME_OWNER_LABEL = os.environ.get("ME_OWNER_LABEL", "owner-rino")


def my_open_issues() -> list[dict]:
    return search(f'labels = "{ME_OWNER_LABEL}" AND statusCategory != Done ORDER BY due ASC')


def all_open_issues() -> list[dict]:
    return search("statusCategory != Done ORDER BY due ASC", limit=100)


def done_issues() -> list[dict]:
    return search("statusCategory = Done ORDER BY updated DESC", limit=100)


def blocked_issues() -> list[dict]:
    return search('statusCategory != Done AND (labels = "blocked" OR status = "Blocked") ORDER BY due ASC')


def overdue_issues() -> list[dict]:
    return search("duedate < now() AND statusCategory != Done ORDER BY due ASC")


def due_tomorrow_issues() -> list[dict]:
    """Open issues whose due date is tomorrow (the 17:00 reminder)."""
    return search('duedate >= startOfDay("+1d") AND duedate <= endOfDay("+1d") '
                  "AND statusCategory != Done ORDER BY due ASC")


def stale_issues(days: int = 7) -> list[dict]:
    """Open issues not updated in the last `days` days — nudge the owner."""
    return search(f"statusCategory != Done AND updated <= -{days}d ORDER BY updated ASC", limit=100)


# --------------------------------------------------------------- write side --
# Creating/assigning initiatives. Writes are gated by ALLOW_WRITES in main.py.

def project_key() -> str | None:
    with _client() as c:
        r = c.get(f"{SITE}/rest/api/3/project/search")
        if r.status_code == 200:
            vals = r.json().get("values", [])
            if vals:
                return vals[0]["key"]
    return None


def _label_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "unknown"


def owner_label(name: str) -> str:
    return "owner-" + _label_slug(name)


def find_assignable_user(query: str, key: str | None = None) -> dict | None:
    """Resolve a real Jira account by name/email so we can assign for real."""
    key = key or project_key()
    with _client() as c:
        r = c.get(f"{SITE}/rest/api/3/user/assignable/search",
                  params={"project": key, "query": query})
        if r.status_code == 200 and r.json():
            u = r.json()[0]
            return {"accountId": u.get("accountId"), "displayName": u.get("displayName")}
    return None


_ME_CACHE: dict = {}


def myself() -> dict | None:
    """The token owner's account — the default assignee ('assign to yourself')."""
    if "me" not in _ME_CACHE:
        with _client() as c:
            r = c.get(f"{SITE}/rest/api/3/myself")
            _ME_CACHE["me"] = ({"accountId": r.json().get("accountId"),
                                "displayName": r.json().get("displayName")}
                               if r.status_code == 200 else None)
    return _ME_CACHE["me"]


def find_epic(name: str, key: str | None = None) -> str | None:
    """Resolve an Epic by name (the funnel stage / project) to its issue key."""
    if not name:
        return None
    key = key or project_key()
    with _client() as c:
        r = c.get(f"{SITE}/rest/api/3/search/jql",
                  params={"jql": f'project = {key} AND issuetype = Epic AND summary ~ "{name}"',
                          "maxResults": 5, "fields": "summary"})
        if r.status_code == 200:
            for i in r.json().get("issues", []):
                if (i["fields"]["summary"] or "").lower() == name.lower():
                    return i["key"]
            issues = r.json().get("issues", [])
            if issues:
                return issues[0]["key"]
    return None


def _dedupe_labels(labels: list[str]) -> list[str]:
    out = []
    seen = set()
    for label in labels:
        if not label:
            continue
        label = _label_slug(label)
        if label not in seen:
            out.append(label)
            seen.add(label)
    return out


def _attempt_fields(base: dict, parent: dict, due: str | None) -> list[dict]:
    """Generate rich-to-minimal field attempts for forgiving Jira projects."""
    variants = []
    variants.append({**base, **parent, **({"duedate": due} if due else {})})
    variants.append({**base, **parent})
    variants.append({**base, **({"duedate": due} if due else {})})
    variants.append(base)
    # Last-resort variants without description, because some project screens reject it.
    if "description" in base:
        no_desc = {k: v for k, v in base.items() if k != "description"}
        variants.extend([
            {**no_desc, **parent, **({"duedate": due} if due else {})},
            {**no_desc, **parent},
            {**no_desc, **({"duedate": due} if due else {})},
            no_desc,
        ])
    return variants


def create_issue(summary: str, itype: str = "Task", stage: str | None = None,
                 owner: str | None = None, due: str | None = None,
                 assignee_id: str | None = None, epic_key: str | None = None,
                 description: str | None = None,
                 extra_labels: list[str] | None = None,
                 labels_extra: list[str] | None = None) -> dict:
    """Create an initiative or investigation task.

    Labels carry owner/stage/contract metadata; epic_key parents it to a funnel
    Epic when the project supports Epics; assignee_id sets a real assignee.
    """
    key = project_key()
    if not key:
        return {"error": "no Jira project found"}
    labels = list(extra_labels or []) + list(labels_extra or [])
    if owner:
        labels.append(owner_label(owner))
    if stage:
        labels.append("stage-" + stage.strip().lower())
    base = {"project": {"key": key}, "summary": summary,
            "issuetype": {"name": itype}, "labels": _dedupe_labels(labels)}
    adf = _adf_doc(description)
    if adf:
        base["description"] = adf
    if assignee_id:
        base["assignee"] = {"accountId": assignee_id}
    parent = {"parent": {"key": epic_key}} if epic_key else {}
    with _client() as c:
        last = ""
        for fields in _attempt_fields(base, parent, due):
            r = c.post(f"{SITE}/rest/api/3/issue", json={"fields": fields})
            if r.status_code < 300:
                k = r.json()["key"]
                return {"key": k, "url": f"{SITE}/browse/{k}", "labels": base["labels"],
                        "assignee_id": assignee_id, "epic_key": epic_key if parent else None}
            last = f"{r.status_code} {r.text[:160]}"
    return {"error": last}


def assign_issue(issue_key: str, assignee_id: str | None = None,
                 owner: str | None = None) -> dict:
    """Assign an existing initiative: set a real assignee and/or owner label."""
    result = {"key": issue_key, "assigned_real": False, "owner_label": None}
    with _client() as c:
        if assignee_id:
            r = c.put(f"{SITE}/rest/api/3/issue/{issue_key}/assignee",
                      json={"accountId": assignee_id})
            result["assigned_real"] = r.status_code < 300
            if r.status_code >= 300:
                result["error"] = f"assignee {r.status_code} {r.text[:120]}"
        if owner:
            lbl = owner_label(owner)
            r = c.put(f"{SITE}/rest/api/3/issue/{issue_key}",
                      json={"update": {"labels": [{"add": lbl}]}})
            if r.status_code < 300:
                result["owner_label"] = lbl
            else:
                result["error"] = f"label {r.status_code} {r.text[:120]}"
    return result


def find_open_investigation(stage: str, month: str | None = None,
                            metric_slug: str | None = None, metric: str | None = None) -> dict | None:
    """Find the existing open investigation for a stage/month to avoid duplicates."""
    if metric and not metric_slug:
        metric_slug = str(metric).replace("_rate_pct", "-rate").replace("_", "-")
    labels = ["investigation", f"stage-{stage.strip().lower()}"]
    if month:
        labels.append("month-" + month)
    if metric_slug:
        labels.append("metric-" + metric_slug)
    label_clause = " AND ".join(f'labels = "{_label_slug(l)}"' for l in labels)
    jql = f"statusCategory != Done AND {label_clause} ORDER BY updated DESC"
    try:
        found = search(jql, limit=5)
    except Exception:  # noqa: BLE001
        return None
    return found[0] if found else None


def add_comment(issue_key: str, body: str) -> dict:
    """Add a plain-text/markdown-ish comment to an issue."""
    with _client() as c:
        r = c.post(f"{SITE}/rest/api/3/issue/{issue_key}/comment",
                   json={"body": _adf_doc(body)})
        if r.status_code < 300:
            return {"key": issue_key, "commented": True}
        return {"key": issue_key, "commented": False, "error": f"{r.status_code} {r.text[:160]}"}


# Compatibility alias.
def comment_issue(issue_key: str, body: str) -> dict:
    return add_comment(issue_key, body)
