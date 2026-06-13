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


# ----------------------------------------------------- lending-funnel data
# Initiatives to improve the loan application funnel
# (applied -> docs -> approved -> disbursed), plus cross-cutting analytics work.
# Each is tagged with: owner-<name> (who's accountable), stage-<funnel stage>,
# and optional blocked. Priority encodes CRITICALITY. Due date encodes the
# on-track signal (a past due date on an open item = off track).
#   (summary, type, priority, due_in_days, labels, target_status)
ISSUES = [
    # --- applied stage (top of funnel: getting people to start & submit) ---
    ("A/B test: simplified loan application form", "Story", "High", 6,
     ["owner-mai", "stage-applied"], "To Do"),
    ("Fix Vietnamese-character bug in application export", "Bug", "Medium", 4,
     ["owner-nam", "stage-applied"], "To Do"),
    ("Re-engagement flow for abandoned applications", "Story", "Medium", 10,
     ["owner-mai", "stage-applied"], "To Do"),
    ("Reduce duplicate OTP sends blocking application start", "Task", "Medium", 7,
     ["owner-linh", "stage-applied"], "To Do"),
    # --- docs stage (the known leak: document upload drop-off) ---
    ("Reduce web docs-upload abandonment", "Story", "Highest", 2,
     ["owner-linh", "stage-docs"], "In Progress"),
    ("Pre-fill KYC from existing customer data", "Story", "High", 8,
     ["owner-linh", "stage-docs"], "To Do"),
    ("Document upload: support HEIC/PDF on mobile", "Story", "High", 3,
     ["owner-mai", "stage-docs"], "In Progress"),
    ("Update KYC document checklist for new circular", "Task", "High", 1,
     ["owner-linh", "stage-docs", "compliance"], "To Do"),
    # --- approved stage (underwriting / approval rate) ---
    ("Lift motorbike-segment approval rate", "Story", "Highest", 3,
     ["owner-hathy", "stage-approved"], "In Progress"),
    ("Approval SLA dashboard for underwriting", "Story", "Medium", 9,
     ["owner-hathy", "stage-approved"], "To Do"),
    ("Underwriting auto-decline rules review", "Task", "High", 6,
     ["owner-hathy", "stage-approved"], "To Do"),
    # --- disbursed stage (bottom: getting approved loans paid out) ---
    ("Cut disbursement drop-off at e-sign step", "Task", "High", 4,
     ["owner-nam", "stage-disbursed"], "To Do"),
    ("Disbursement webhook idempotency keys", "Task", "High", 0,
     ["owner-nam", "stage-disbursed"], "In Progress"),
    ("Renew TLS certs for partner disbursement API", "Task", "Highest", -2,
     ["owner-nam", "stage-disbursed", "blocked", "infra"], "To Do"),
    # --- cross-cutting (instrumentation, reporting, infra) ---
    ("Instrument funnel events end-to-end", "Task", "High", 1,
     ["owner-rino", "stage-crosscut"], "In Progress"),
    ("Migrate risk-score batch job off legacy cron", "Task", "High", 2,
     ["owner-rino", "stage-crosscut", "blocked", "infra"], "To Do"),
    ("Funnel weekly metrics auto-report", "Story", "Medium", 12,
     ["owner-rino", "stage-crosscut"], "To Do"),
    # --- done pile (recent wins, for momentum / 'what changed') ---
    ("Launch docs-upload progress indicator", "Story", "High", -3,
     ["owner-linh", "stage-docs"], "Done"),
    ("Add motorbike-loan approval monitor", "Task", "High", -4,
     ["owner-hathy", "stage-approved"], "Done"),
    ("Baseline funnel conversion report", "Task", "Medium", -6,
     ["owner-rino", "stage-crosscut"], "Done"),
    ("Fix approval-rate calculation rounding", "Bug", "Medium", -5,
     ["owner-hathy", "stage-approved"], "Done"),
]

PAGES = [
    ("Funnel initiative charter", """
<h2>Why this program exists</h2>
<p>End-to-end application conversion is <strong>47.6%</strong> (applied → disbursed).
The biggest single leak is <strong>document upload on web</strong>. This program
groups every initiative that moves a funnel-stage metric, with one accountable
owner each, so the lending lead can see at a glance what's in flight and what's at risk.</p>
<h2>Stages &amp; current owners</h2>
<ul>
<li><strong>Applied</strong> (start &amp; submit) — Mai, Nam, Linh</li>
<li><strong>Docs</strong> (KYC / upload) — Linh, Mai</li>
<li><strong>Approved</strong> (underwriting) — Hathy</li>
<li><strong>Disbursed</strong> (payout) — Nam</li>
<li><strong>Cross-cutting</strong> (instrumentation, reporting) — Rino</li>
</ul>
<p>Criticality = Jira priority. Anything <em>Highest/High</em> and past its due date
or <em>blocked</em> is escalated in the daily LM digest.</p>
"""),
    ("Decision log — Funnel", """
<h2>Decision: docs-upload is the #1 conversion priority this quarter</h2>
<p><strong>Date:</strong> {d1} · <strong>Status:</strong> APPROVED</p>
<p>Web document upload shows the steepest drop-off in the funnel. Decision: treat
<strong>"Reduce web docs-upload abandonment"</strong> as the top initiative; pre-fill
KYC and mobile file-type support follow. Owner: Linh.</p>
<h2>Decision: switch approval early-warning to a vintage-based view</h2>
<p><strong>Date:</strong> {d2} · <strong>Status:</strong> APPROVED</p>
<p>Recent motorbike originations approve far below older cohorts (51% vs 70%).
Decision: track approval rate by vintage so deterioration is caught early.
Owner: Hathy. Revisit after Q3.</p>
"""),
    ("Sprint planning — funnel initiatives", """
<p><strong>Goal:</strong> ship the docs-upload fixes (progress indicator already live)
and unblock the partner disbursement TLS renewal.</p>
<ul><li>Capacity: 5 contributors across the funnel stages</li>
<li>Carry-over: risk-score batch migration (blocked on infra)</li>
<li><strong>Top risk:</strong> TLS cert renewal for the partner disbursement API is
blocked AND overdue — escalate if vendor doesn't reply by {d3}.</li></ul>
"""),
    ("Incident postmortem — duplicate disbursement alerts (2026-06-03)", """
<h2>Summary</h2><p>The payment gateway retried webhooks during a maintenance window;
our consumer lacked idempotency keys, causing duplicate alert storms at the
disbursed stage (no duplicate payouts — reconciliation caught them).</p>
<h2>Action items</h2>
<ul><li>Add idempotency keys to the disbursement webhook consumer (in progress)</li>
<li>Silence alert storms via a 5-minute dedup window</li></ul>
"""),
    ("Funnel metric definitions", """
<ul>
<li><strong>Stage conversion</strong> = entered next stage ÷ entered this stage.</li>
<li><strong>Docs drop-off</strong> = applications that reach upload but never submit docs.</li>
<li><strong>Approval rate</strong> = approved ÷ fully-documented, by product &amp; vintage.</li>
<li><strong>Disbursement drop-off</strong> = approved loans not paid out within 7 days.</li>
<li>Owner of a metric = owner of the initiative tagged to that stage.</li>
</ul>
"""),
    ("Team working agreements", """
<ul><li>Every initiative has exactly one <em>owner-</em> label and a due date before work starts.</li>
<li>Blockers flagged with the <em>blocked</em> label the same day they appear.</li>
<li>Decisions go in the Decision log within 24h — if it's not written down, it didn't happen.</li></ul>
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


def reset_jira(c: httpx.Client, key: str):
    """Delete every issue in the project (synthetic workspace — safe to wipe)."""
    r = c.get(f"{SITE}/rest/api/3/search/jql",
              params={"jql": f"project = {key}", "maxResults": 200, "fields": "summary"})
    issues = r.json().get("issues", []) if r.status_code == 200 else []
    for i in issues:
        dr = c.delete(f"{SITE}/rest/api/3/issue/{i['key']}")
        print(("deleted: " if dr.status_code < 300 else f"FAILED del ({dr.status_code}): ") + i["key"])
    print(f"reset: removed {len(issues)} Jira issue(s)")


def reset_confluence(c: httpx.Client, sid: str):
    """Delete every page in the space (synthetic workspace — safe to wipe)."""
    r = c.get(f"{SITE}/wiki/api/v2/spaces/{sid}/pages", params={"limit": 100})
    pages = r.json().get("results", []) if r.status_code == 200 else []
    for p in pages:
        dr = c.delete(f"{SITE}/wiki/api/v2/pages/{p['id']}")
        print(("deleted page: " if dr.status_code < 300 else f"FAILED del ({dr.status_code}): ") + p["title"])
    print(f"reset: removed {len(pages)} Confluence page(s)")


if __name__ == "__main__":
    do_reset = os.environ.get("SEED_RESET", "").lower() in ("1", "true", "yes")
    with httpx.Client(timeout=30, auth=AUTH) as c:
        if do_reset:
            print("== Reset (SEED_RESET set) ==")
            reset_jira(c, jira_project_key(c))
            reset_confluence(c, confluence_space_id(c))
        print("== Jira =="); seed_jira(c)
        print("== Confluence =="); seed_confluence(c)
        print("Seeding complete.")
