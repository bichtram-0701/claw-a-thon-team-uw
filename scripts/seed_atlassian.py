"""Seed the free Atlassian workspace with a synthetic sprint.

Run by .github/workflows/atlassian-seed.yml (the dev sandbox can't reach
Atlassian). Idempotent-ish: skips issues/pages whose titles already exist.
All content is fictional — a believable fintech squad, no real people/data.
"""
import os
import sys
from datetime import date, timedelta

import httpx

FUNNEL_EPICS = ["Traffic", "Submission", "Approval", "Disbursement"]   # one owner each
SHARED_EPICS = {"Data & Platform"}                                     # can have many owners

SITE = os.environ["ATLASSIAN_SITE"].rstrip("/")
AUTH = (os.environ["ATLASSIAN_EMAIL"], os.environ["ATLASSIAN_TOKEN"])
TODAY = date.today()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


# ----------------------------------------------------- business-funnel data
# Initiatives to improve the demo funnel
# (traffic -> submission -> approval -> disbursement), plus cross-cutting work.
# Simple model: every initiative is a Task. Each is tagged with owner-<name>
# (who's accountable), stage-<funnel stage>, and optional blocked. There is no
# priority field — URGENCY comes from the due date (overdue or due-soon) and the
# blocked flag. Status is one of: To Do / In Progress / In Review / Done.
#   (summary, due_in_days, labels, target_status)
ISSUES = [
    # --- traffic stage (eligible traffic data: logging, reconciliation) ---
    ("Bug: gap between raw traffic and eligible-traffic counts", 5,
     ["stage-traffic", "data"], "In Progress"),
    ("Build eligible-traffic daily log for the E2E funnel", 9,
     ["stage-traffic", "data"], "To Do"),
    ("Monitor traffic volume vs monthly forecast", 7,
     ["stage-traffic", "monitoring"], "To Do"),
    # --- submission stage (submission log, score mapping, schema) ---
    ("Bug: score mapping from traffic step to pre-submission step", 2,
     ["stage-submission", "data"], "In Progress"),
    ("Data lineage for submission log (applied -> submitted)", 6,
     ["stage-submission", "data"], "To Do"),
    ("Schema: standardize submission-stage event log", 3,
     ["stage-submission", "schema"], "In Review"),
    ("Bug: null rejection reasons in submission log", 4,
     ["stage-submission", "data"], "To Do"),
    ("Monitor docs-upload drop-off in the submission log", 1,
     ["stage-submission", "monitoring"], "To Do"),
    # --- approval stage (approval analytics, rejection reasons, backtest) ---
    ("Bug: approved-user count discrepancy vs partner report", 2,
     ["stage-approval", "data"], "In Progress"),
    ("Monitor approval rate by vintage (standard-application cohort)", 8,
     ["stage-approval", "monitoring"], "To Do"),
    ("Rejection-reason classification for declined applications", 6,
     ["stage-approval", "data"], "In Review"),
    ("Backtest approval-model output vs actuals", 10,
     ["stage-approval", "data"], "To Do"),
    # --- disbursement stage (reconciliation against partner records) ---
    ("Reconcile final outcome value vs partner statement", 4,
     ["stage-disbursement", "data"], "To Do"),
    ("Bug: NimbusPay disbursement records missing in funnel log", 0,
     ["stage-disbursement", "data"], "In Progress"),
    ("Bug: disbursement timestamp mismatch (verification status map)", -2,
     ["stage-disbursement", "data", "blocked"], "To Do"),
    # --- data & platform (build / monitor shared data assets) ---
    ("Centralize all model outputs from AsterScore into the Risk database", 1,
     ["stage-crosscut", "data"], "In Progress"),
    ("Schema convention for model-output tables", 5,
     ["stage-crosscut", "schema"], "To Do"),
    ("Alert: missing records in the E2E funnel log", 2,
     ["stage-crosscut", "monitoring", "blocked"], "To Do"),
    ("Refactor log field user_onboarding_info -> user_approval_info", 12,
     ["stage-crosscut", "data"], "To Do"),
    # --- done pile (recent wins, for momentum / 'what changed') ---
    ("Baseline E2E funnel conversion log", -3,
     ["stage-crosscut", "data"], "Done"),
    ("Add standard-application approval-rate monitor", -4,
     ["stage-approval", "monitoring"], "Done"),
    ("Data lineage map: traffic -> disbursement", -6,
     ["stage-crosscut", "data"], "Done"),
    ("Fix approval-rate rounding in the weekly report", -5,
     ["stage-approval", "data"], "Done"),
]

PAGES = [
    ("Funnel stage definitions", """
<p>The demo funnel has four stages. Conversion is measured between consecutive stages.</p>
<table data-layout="default"><tbody>
<tr><th>Stage</th><th>Definition</th></tr>
<tr><td><strong>Traffic</strong></td><td>Users who are eligible and enter the application flow (eligible traffic only).</td></tr>
<tr><td><strong>Submission</strong></td><td>Users whose application is successfully submitted and received by the partner.</td></tr>
<tr><td><strong>Approval</strong></td><td>Users who are approved by the partner.</td></tr>
<tr><td><strong>Disbursement</strong></td><td>Users whose approved application reaches the final outcome event in the demo.</td></tr>
</tbody></table>
<p><strong>Rates:</strong> Submission = Submission/Traffic · Approval = Approval/Submission ·
Disbursement = Disbursement/Approval · End-to-end (E2E) = Disbursement/Traffic.</p>
"""),
    ("Funnel initiative charter", """
<h2>Why this program exists</h2>
<p>End-to-end (Traffic → Disbursement) conversion sits around <strong>3.8–4.4%</strong>,
and the steepest drop is at <strong>Submission</strong> (document upload on web). This
program groups every initiative that moves a funnel-stage metric, with one accountable
owner each, so the business lead can see at a glance what's in flight and what's at risk.</p>
<h2>Stages &amp; current owners</h2>
<ul>
<li><strong>Traffic</strong> (eligible users entering the flow) — Mai, Linh</li>
<li><strong>Submission</strong> (submit &amp; documents) — Linh, Mai, Nam</li>
<li><strong>Approval</strong> (partner review) — Hathy</li>
<li><strong>Disbursement</strong> (final outcome event) — Nam</li>
<li><strong>Cross-cutting</strong> (instrumentation, reporting) — Rino</li>
</ul>
<p>Urgency = the due date. Anything <em>overdue</em> or <em>blocked</em> is escalated
in the daily LM digest; items due within 3 days are flagged as due-soon. Every
initiative is a single Jira <em>Task</em> (no priority field) and moves through
To&nbsp;Do → In&nbsp;Progress → In&nbsp;Review → Done.</p>
"""),
    ("Decision log — Funnel", """
<h2>Decision: instrument the submission step before optimising it</h2>
<p><strong>Date:</strong> {d1} · <strong>Status:</strong> APPROVED</p>
<p>The submission step shows the steepest drop-off, but score mapping from traffic
to pre-submission is unreliable. Decision: fix the submission-log score mapping and
stand up data lineage first, then monitor docs-upload drop-off. Owner: the
Submission Epic owner.</p>
<h2>Decision: monitor approval rate by vintage</h2>
<p><strong>Date:</strong> {d2} · <strong>Status:</strong> APPROVED</p>
<p>Recent standard applications approve far below older cohorts (51% vs 70%).
Decision: track approval rate by vintage so deterioration is caught early.
Owner: the Approval Epic owner. Revisit after Q3.</p>
"""),
    ("Sprint planning — funnel initiatives", """
<p><strong>Goal:</strong> stand up the E2E funnel log (traffic -> submission ->
approval -> disbursement) and standardise the submission-stage schema.</p>
<ul><li>Carry-over: centralising model outputs into the Risk database (in progress)</li>
<li><strong>Top risk:</strong> the disbursement timestamp-mismatch bug (verification status map)
is blocked AND overdue — escalate by {d3}.</li>
<li>Watch: the "missing records in the E2E funnel log" alert is blocked on upstream data.</li></ul>
"""),
    ("Incident postmortem — duplicate disbursement alerts (2026-06-03)", """
<h2>Summary</h2><p>The payment gateway retried webhooks during a maintenance window;
our consumer lacked idempotency keys, causing duplicate alert storms at the
final stage (no duplicate outcomes — reconciliation caught them).</p>
<h2>Action items</h2>
<ul><li>Add idempotency keys to the disbursement webhook consumer (in progress)</li>
<li>Silence alert storms via a 5-minute dedup window</li></ul>
"""),
    ("Funnel metric definitions", """
<ul>
<li><strong>Submission rate</strong> = Submission ÷ Traffic.</li>
<li><strong>Approval rate</strong> = Approval ÷ Submission (by product &amp; vintage).</li>
<li><strong>Disbursement rate</strong> = Disbursement ÷ Approval.</li>
<li><strong>End-to-end (E2E) rate</strong> = Disbursement ÷ Traffic.</li>
<li><strong>Avg ticket size</strong> = Disbursement amount ÷ Disbursement count.</li>
<li>Owner of a stage metric = owner of the initiative tagged to that stage.</li>
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


def valid_issue_types(c: httpx.Client, key: str) -> set:
    """Issue-type names the project actually accepts. Team-managed projects often
    lack 'Story', which silently fails creation — so we map to what's available."""
    r = c.get(f"{SITE}/rest/api/3/issue/createmeta",
              params={"projectKeys": key, "expand": "projects.issuetypes"})
    if r.status_code == 200:
        projs = r.json().get("projects", [])
        if projs:
            names = {t["name"] for t in projs[0].get("issuetypes", [])}
            if names:
                return names
    # newer endpoint fallback
    r = c.get(f"{SITE}/rest/api/3/issue/createmeta/{key}/issuetypes")
    if r.status_code == 200:
        return {t["name"] for t in r.json().get("values", [])}
    return set()


def _map_type(itype: str, valid: set) -> str:
    if not valid or itype in valid:
        return itype
    lower = {v.lower(): v for v in valid}
    if itype.lower() in lower:
        return lower[itype.lower()]
    for pref in ("Task", "Story", "Bug"):       # Story->Task etc.
        if pref in valid:
            return pref
    return sorted(valid)[0]


# Each funnel stage is an Epic (swimlane); cross-cutting work lives in its own Epic.
STAGE_TO_EPIC = {
    "traffic": "Traffic",
    "submission": "Submission",
    "approval": "Approval",
    "disbursement": "Disbursement",
    "crosscut": "Data & Platform",
}


def _stage_label(labels: list[str]) -> str | None:
    for l in labels:
        if l.lower().startswith("stage-"):
            return l.split("-", 1)[1].lower()
    return None


def ensure_epics(c: httpx.Client, key: str, valid: set) -> dict:
    """Create one Epic per stage (idempotent). Returns {epic_name: epic_key}.
    If the project has no Epic issue type, returns {} and tasks fall back to
    stage labels only."""
    if "Epic" not in valid:
        print("(project has no Epic issue type — tasks will use stage labels only)")
        return {}
    r = c.get(f"{SITE}/rest/api/3/search/jql",
              params={"jql": f"project = {key} AND issuetype = Epic", "maxResults": 50, "fields": "summary"})
    existing = ({i["fields"]["summary"]: i["key"] for i in r.json().get("issues", [])}
                if r.status_code == 200 else {})
    out = {}
    for name in dict.fromkeys(STAGE_TO_EPIC.values()):   # preserve order, dedupe
        if name in existing:
            out[name] = existing[name]; print("epic exists:", existing[name], name); continue
        rr = c.post(f"{SITE}/rest/api/3/issue", json={"fields": {
            "project": {"key": key}, "summary": name, "issuetype": {"name": "Epic"}}})
        if rr.status_code < 300:
            out[name] = rr.json()["key"]; print("epic created:", out[name], name)
        else:
            print("epic FAILED:", name, rr.status_code, rr.text[:140])
    return out


def assignable_users(c: httpx.Client, key: str) -> list[dict]:
    """Real members who can be assigned in this project (humans only)."""
    r = c.get(f"{SITE}/rest/api/3/user/assignable/search",
              params={"project": key, "maxResults": 50})
    if r.status_code != 200:
        return []
    return [{"accountId": u["accountId"], "name": u.get("displayName")}
            for u in r.json()
            if u.get("accountId") and u.get("accountType", "atlassian") == "atlassian"]


def seed_jira(c: httpx.Client):
    key = jira_project_key(c)
    have = existing_summaries(c, key)
    me = c.get(f"{SITE}/rest/api/3/myself").json()["accountId"]
    valid = valid_issue_types(c, key)
    print("valid issue types:", ", ".join(sorted(valid)) or "(none discovered)")
    epics = ensure_epics(c, key, valid)

    # Distribute real users: each funnel Epic gets ONE owner (round-robin over the
    # real members); shared/unsorted work is spread across everyone.
    users = assignable_users(c, key) or [{"accountId": me, "name": "me"}]
    print("assignable users:", ", ".join(u["name"] or u["accountId"] for u in users))
    epic_owner = {name: users[i % len(users)] for i, name in enumerate(FUNNEL_EPICS)}
    for name, u in epic_owner.items():
        print(f"  Epic owner: {name} -> {u['name']}")
    _shared = {"i": 0}

    def pick_assignee(epic_name):
        if epic_name in epic_owner:
            return epic_owner[epic_name]["accountId"]
        u = users[_shared["i"] % len(users)]   # shared/unsorted: rotate everyone
        _shared["i"] += 1
        return u["accountId"]

    mapped = _map_type("Task", valid)   # simple model: every initiative is a Task
    created = failed = skipped = 0
    for summary, due_in, labels, status in ISSUES:
        if summary in have:
            print("skip (exists):", summary); skipped += 1; continue
        epic_name = STAGE_TO_EPIC.get(_stage_label(labels) or "")
        # assignee is the source of truth now — drop owner-* labels.
        clean_labels = [l for l in labels if not l.lower().startswith("owner-")]
        base = {"project": {"key": key}, "summary": summary,
                "issuetype": {"name": mapped}, "labels": clean_labels,
                "assignee": {"accountId": pick_assignee(epic_name)}}
        epic_key = epics.get(epic_name) if epic_name else None
        parent = {"parent": {"key": epic_key}} if epic_key else {}
        # richest first; drop parent / duedate if the project rejects them, so a
        # task always gets created (its stage label still drives grouping).
        attempts = [
            {**base, **parent, "duedate": d(due_in)},
            {**base, **parent},
            {**base, "duedate": d(due_in)},
            base,
        ]
        ikey = None
        last = ""
        for fields in attempts:
            r = c.post(f"{SITE}/rest/api/3/issue", json={"fields": fields})
            if r.status_code < 300:
                ikey = r.json()["key"]; break
            last = f"{r.status_code} {r.text[:160]}"
        if not ikey:
            print("FAILED:", summary, "|", last); failed += 1; continue
        epic_note = f" [{epic_name}]" if epic_key else (f" (label {epic_name}, no parent)" if epic_name else "")
        print("created:", ikey, summary, epic_note); created += 1
        if status != "To Do":
            transition_to(c, ikey, status)
    print(f"Jira seed summary: {created} created, {skipped} skipped, {failed} failed; "
          f"{len(epics)} epics")


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
    """Delete every issue in the project (synthetic workspace — safe to wipe).
    Delete non-Epics first, then Epics, so a parent is never removed before its
    children (which would error or orphan them)."""
    r = c.get(f"{SITE}/rest/api/3/search/jql",
              params={"jql": f"project = {key}", "maxResults": 200, "fields": "summary,issuetype"})
    issues = r.json().get("issues", []) if r.status_code == 200 else []
    issues.sort(key=lambda i: (i.get("fields", {}).get("issuetype", {}) or {}).get("name") == "Epic")
    for i in issues:
        dr = c.delete(f"{SITE}/rest/api/3/issue/{i['key']}", params={"deleteSubtasks": "true"})
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
