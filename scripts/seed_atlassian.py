"""Seed the free Atlassian workspace with a synthetic sprint.

Run by .github/workflows/atlassian-seed.yml (the dev sandbox can't reach
Atlassian). Idempotent-ish: skips issues/pages whose titles already exist.
All content is fictional — a believable fintech squad, no real people/data.
"""
import os
import sys
from datetime import date, timedelta

import httpx

SITE = os.environ["ATLASSIAN_SITE"].rstrip("/")
AUTH = (os.environ["ATLASSIAN_EMAIL"], os.environ["ATLASSIAN_TOKEN"])
TODAY = date.today()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


# --------------------------------------------------------------- sprint data
# (key, summary, type, priority, due_in_days, labels, target_status)
ISSUES = [
    ("Implement OTP rate-limiting on login", "Task", "Highest", -1, ["security"], "In Progress"),
    ("Fix duplicate webhook events from payment gateway", "Bug", "Highest", 0, [], "In Progress"),
    ("Migrate risk-score batch job off legacy cron", "Task", "High", 2, ["blocked", "infra"], "To Do"),
    ("Q3 lending dashboard: add vintage view", "Story", "High", 3, [], "In Progress"),
    ("Update KYC document checklist for new circular", "Task", "High", 1, ["compliance"], "To Do"),
    ("Refactor repayment schedule calculator", "Task", "Medium", 5, [], "To Do"),
    ("A/B test: simplified loan application form", "Story", "Medium", 6, [], "To Do"),
    ("Add Confluence runbook links to PagerDuty alerts", "Task", "Low", 8, ["infra"], "To Do"),
    ("Investigate spike in docs-upload abandonment (web)", "Task", "High", 2, [], "In Progress"),
    ("Patch CSV export encoding bug (Vietnamese chars)", "Bug", "Medium", 4, [], "To Do"),
    ("Renew TLS certs for partner API", "Task", "Highest", -2, ["blocked", "infra", "security"], "To Do"),
    ("Write integration tests for disbursement service", "Task", "Medium", 7, [], "To Do"),
    ("Design review: collections reminder flow v2", "Story", "Medium", 9, [], "To Do"),
    ("Archive 2024 loan tapes to cold storage", "Task", "Low", 12, [], "To Do"),
    ("Spike: evaluate vector search for support macros", "Story", "Low", 10, [], "To Do"),
    # done pile
    ("Fix NPL ratio rounding in weekly report", "Bug", "High", -3, [], "Done"),
    ("Add motorbike-loan approval monitor", "Task", "High", -4, [], "Done"),
    ("Set up staging environment for risk API", "Task", "Medium", -5, ["infra"], "Done"),
    ("Document incident postmortem 2026-06-03", "Task", "High", -6, [], "Done"),
    ("Upgrade pandas in analytics image", "Task", "Low", -7, [], "Done"),
]

PAGES = [
    ("Decision log — Risk model", """
<h2>Decision: switch NPL early-warning to vintage-based model</h2>
<p><strong>Date:</strong> {d1} · <strong>Status:</strong> APPROVED</p>
<p>We compared the flat 90-DPD threshold model against a vintage-based approach.
Decision: adopt the <strong>vintage-based model</strong> for early warning, because recent
originations showed deterioration invisible to the flat model (motorbike segment:
51% vs 70% approval-cohort performance). Owner: Hathy. Revisit after Q3.</p>
<h2>Decision: keep risk thresholds out of the public repo</h2>
<p><strong>Date:</strong> {d2} · <strong>Status:</strong> APPROVED</p>
<p>Production thresholds live in the internal config service only. Public/demo
repos use placeholder values.</p>
"""),
    ("Sprint 12 planning notes", """
<p><strong>Sprint goal:</strong> close the security backlog (OTP rate-limiting, TLS renewal)
and ship the vintage view on the lending dashboard.</p>
<ul><li>Capacity: 3 engineers, no holidays</li>
<li>Carry-over: webhook duplicate bug (gateway vendor slow to respond)</li>
<li>Risk: TLS renewal blocked on infra ticket with vendor — escalate if no reply by {d3}</li></ul>
"""),
    ("Incident postmortem — duplicate disbursement alerts (2026-06-03)", """
<h2>Summary</h2><p>Payment gateway retried webhooks during their maintenance window;
our consumer lacked idempotency keys, causing duplicate alert storms (no duplicate
payouts — reconciliation caught them).</p>
<h2>Action items</h2>
<ul><li>Add idempotency keys to webhook consumer (ticket filed)</li>
<li>Silence alert storms via 5-minute dedup window</li></ul>
"""),
    ("API design decision — partner disbursement API v2", """
<p><strong>Decision ({d4}):</strong> v2 uses async job + callback instead of synchronous
disbursement. Rationale: partner timeouts caused phantom retries in v1. Breaking
change announced for Q4; v1 sunset after two quarters of dual-running.</p>
"""),
    ("Team working agreements", """
<ul><li>Standup async in channel by 09:30, blockers flagged with the <em>blocked</em> label in Jira</li>
<li>Tickets must have due dates before sprint start</li>
<li>Decisions go in the Decision log within 24h — if it's not written down, it didn't happen</li></ul>
"""),
    ("Retro — Sprint 11", """
<p><strong>Went well:</strong> deploy pipeline now fully automated; zero failed releases.</p>
<p><strong>Needs work:</strong> too much WIP — agreed WIP limit of 2 per person.</p>
<p><strong>Experiment for Sprint 12:</strong> agent-generated standup drafts (this project!).</p>
"""),
]


def jira_project_key(c: httpx.Client) -> str:
    r = c.get(f"{SITE}/rest/api/3/project/search"); r.raise_for_status()
    vals = r.json().get("values", [])
    if not vals:
        sys.exit("No Jira project found - create one in the UI first")
    print("Using Jira project:", vals[0]["key"], "-", vals[0]["name"])
    return vals[0]["key"]


def existing_summaries(c: httpx.Client, key: str) -> set:
    r = c.get(f"{SITE}/rest/api/3/search/jql",
              params={"jql": f"project = {key}", "maxResults": 100, "fields": "summary"})
    if r.status_code != 200:
        return set()
    return {i["fields"]["summary"] for i in r.json().get("issues", [])}


def transition_to(c: httpx.Client, issue_key: str, target: str):
    r = c.get(f"{SITE}/rest/api/3/issue/{issue_key}/transitions"); r.raise_for_status()
    for t in r.json().get("transitions", []):
        if t["to"]["name"].lower() == target.lower():
            c.post(f"{SITE}/rest/api/3/issue/{issue_key}/transitions",
                   json={"transition": {"id": t["id"]}})
            return
    print(f"  (no transition to {target} found for {issue_key})")


def seed_jira(c: httpx.Client):
    key = jira_project_key(c)
    have = existing_summaries(c, key)
    me = c.get(f"{SITE}/rest/api/3/myself").json()["accountId"]
    for summary, itype, prio, due_in, labels, status in ISSUES:
        if summary in have:
            print("skip (exists):", summary); continue
        fields = {
            "project": {"key": key},
            "summary": summary,
            "issuetype": {"name": itype},
            "priority": {"name": prio},
            "labels": labels,
            "duedate": d(due_in),
            "assignee": {"accountId": me},
        }
        r = c.post(f"{SITE}/rest/api/3/issue", json={"fields": fields})
        if r.status_code >= 300:
            print("FAILED:", summary, r.status_code, r.text[:200]); continue
        ikey = r.json()["key"]
        print("created:", ikey, summary)
        if status != "To Do":
            transition_to(c, ikey, status)


def confluence_space_id(c: httpx.Client) -> str:
    r = c.get(f"{SITE}/wiki/api/v2/spaces"); r.raise_for_status()
    results = [s for s in r.json().get("results", []) if s.get("type") != "personal"]
    if not results:
        sys.exit("No Confluence space found - create one in the UI first")
    print("Using Confluence space:", results[0]["key"], "-", results[0]["name"])
    return results[0]["id"]


def seed_confluence(c: httpx.Client):
    sid = confluence_space_id(c)
    r = c.get(f"{SITE}/wiki/api/v2/spaces/{sid}/pages", params={"limit": 100})
    have = {p["title"] for p in r.json().get("results", [])} if r.status_code == 200 else set()
    subs = {"d1": d(-9), "d2": d(-8), "d3": d(1), "d4": d(-12)}
    for title, body in PAGES:
        if title in have:
            print("skip (exists):", title); continue
        payload = {"spaceId": sid, "status": "current", "title": title,
                   "body": {"representation": "storage", "value": body.format(**subs)}}
        r = c.post(f"{SITE}/wiki/api/v2/pages", json=payload)
        print(("created: " if r.status_code < 300 else f"FAILED ({r.status_code}): ") + title)


if __name__ == "__main__":
    with httpx.Client(timeout=30, auth=AUTH) as c:
        print("== Jira =="); seed_jira(c)
        print("== Confluence =="); seed_confluence(c)
        print("Seeding complete.")
