"""Offline tests for Funnel Agent — no network, no LLM, no Atlassian.

Stubs the Jira/Confluence clients with synthetic fixtures and forces the LLM
offline. Exercises: intent routing, manager_digest (urgency via due date +
blocked, grouped by Epic), funnel metrics, and create/assign (Epic parent +
assign-to-self default).

Run:  python tests/test_offline.py     (from repo root)
"""
import os
import sys
import types
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fake = types.ModuleType("greennode_agentbase")


class _App:
    def __init__(self, *a, **k):
        self.router = types.SimpleNamespace(routes=[])

    def entrypoint(self, fn):
        return fn

    def ping(self, fn):
        return fn

    def run(self, *a, **k):
        pass


class _Ping:
    HEALTHY = "HEALTHY"


fake.GreenNodeAgentBaseApp = _App
fake.PingStatus = _Ping
fake.RequestContext = object
sys.modules["greennode_agentbase"] = fake

os.environ.update(ATLASSIAN_SITE="https://x.atlassian.net",
                  ATLASSIAN_EMAIL="x@y.z", ATLASSIAN_TOKEN="t" * 192,
                  ALLOW_WRITES="true", JIRA_PROJECT_KEY="UW")
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("LLM_BASE_URL", None)
os.environ.pop("TEAMS_WEBHOOK_URL", None)

import jira_client as jc
import confluence_client as cf
import main as m

_EPIC = {"traffic": "Traffic", "submission": "Submission", "approval": "Approval",
         "completion": "Disbursement", "crosscut": "Data & Platform"}


def _mk(key, summary, status, owner, stage, due, labels=None, blocked_by=None, blocks=None):
    """Mirror jira_client._brief: simple model, epic = the stage's Epic name."""
    labels = (labels or []) + [f"owner-{owner.lower()}", f"stage-{stage}"]
    return {"key": key, "summary": summary, "status": status, "assignee": "Rino Tran",
            "owner": owner, "stage": stage, "epic": _EPIC.get(stage), "due": due,
            "labels": labels, "type": "Task", "blocked_by": blocked_by, "blocks": blocks}


_ISSUES = [
    _mk("UW-1", "Renew TLS certs", "To Do", "Nam", "completion", "2026-01-10", ["blocked", "infra"],
        blocked_by="certificate approval", blocks="secure disbursement webhook"),
    _mk("UW-2", "Reduce docs-upload abandonment", "In Progress", "Linh", "submission", "2026-12-15"),
    _mk("UW-3", "Migrate risk-score batch", "To Do", "Rino", "crosscut", "2026-12-15", ["blocked"]),
    _mk("UW-4", "Instrument funnel events", "In Progress", "Rino", "crosscut", "2026-12-16"),
    _mk("UW-5", "A/B test form", "In Review", "Mai", "submission", "2026-12-20"),
]
_DONE = [_mk("UW-9", "Baseline report", "Done", "Rino", "crosscut", "2026-01-05")]


def _mine():
    return [i for i in _ISSUES if i["owner"] == "Rino" and i["status"] != "Done"]


jc.my_open_issues = _mine
jc.all_open_issues = lambda: list(_ISSUES)
jc.done_issues = lambda: list(_DONE)
jc.blocked_issues = lambda: [i for i in _ISSUES if "blocked" in i["labels"]]
jc.overdue_issues = lambda: [i for i in _ISSUES if i["due"] < "2026-06-13"]
cf.search_pages = lambda q, limit=3: [
    {"title": "Decision log - Funnel", "url": "https://x/wiki/1", "excerpt": "e", "body": "b"}]
cf.recent_pages = lambda limit=8, with_body=False, include_body=False: [
    {"title": "Weekly funnel review", "url": "https://x/wiki/2", "body": "Approval recovery actions"}]

PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1; print("  PASS  " + name)
    else:
        FAIL += 1; print("  FAIL  " + name)


print("routing:")
check("metrics", m.route("show me the funnel metrics") == "metrics")
check("conversion->metrics", m.route("what's the conversion rate?") == "metrics")
check("create", m.route("create a ticket to improve submission") == "create")
check("assign", m.route("assign UW-23 to Mai") == "assign")
check("overview->oversight", m.route("give me the funnel overview") == "oversight")
check("off track->oversight", m.route("what's off track?") == "oversight")
check("assigned-to-me->briefing", m.route("what's assigned to me?") == "briefing")
check("plate->briefing", m.route("what's on my plate?") == "briefing")
check("sprint", m.route("how is the sprint going?") == "sprint")
check("decide->knowledge", m.route("what did we decide about submission?") == "knowledge")
check("standup", m.route("draft my standup") == "standup")
check("daily volume->analyst", m.route("show daily volume in May") == "analyst")
check("day-over-day number->analyst", m.route("can you give me the number day over day in May") == "analyst")
check("why approval drop->analyst", m.route("why did approval drop?") == "analyst")
check("weekly summary->weekly", m.route("summarize everything for weekly meeting") == "weekly")
check("teams reminder->teams", m.route("send off-track reminder to Teams") == "teams")
check("usage guide->help", m.route("how to use this chat") == "help")
check("blocked semantics->oversight", m.route("what does blocked mean here and what is it blocking?") == "oversight")
check("unassigned work->oversight", m.route("what are those 9 open tasks without assignee") == "oversight")
check("gibberish->help", m.route("zzz qwerty") == "help")
check("slash funnel exact", m.route("/funnel show me the funnel metrics") == "metrics")
check("slash metrics removed", m.route("/metrics show me the funnel metrics") == "help")
check("slash query exact", m.route("/query show daily volume in May") == "analyst")
check("slash jira flag exact", m.route("/jira flag the drops and assign owners to investigate") == "flag")
check("natural weekly summary exact", m.route("weekly meeting summary") == "weekly")
check("slash teams exact", m.route("/teams post off-track blockers") == "teams")

print("handler:")
for q, intent in [("funnel overview", "oversight"), ("what's on my plate?", "briefing"),
                  ("how is the sprint going?", "sprint"), ("what did we decide?", "knowledge"),
                  ("draft my standup", "standup"), ("summarize everything for weekly meeting", "weekly"),
                  ("send off-track reminder to Teams", "teams"), ("hello", "help")]:
    r = m.handler({"message": q}, None)
    check(intent + ":success", r.get("status") == "success")
    check(intent + ":intent", r.get("intent") == intent)

print("manager_digest (grouped by Epic, urgency by due/blocked):")
import briefing as bf
md = bf.manager_digest()
check("open=5", md["totals"]["open"] == 5)
check("no critical_open key", "critical_open" not in md["totals"])
check("needs_attention UW-1&UW-3", {i["key"] for i in md["needs_attention_now"]} == {"UW-1", "UW-3"})
check("blocked context retained", next(i for i in md["needs_attention_now"] if i["key"] == "UW-1")["blocked_by"] == "certificate approval")
check("off_track=2", md["totals"]["off_track"] == 2)
check("due_soon in totals", "due_soon" in md["totals"])
check("unassigned fields present", "owner_unassigned_open" in md and "assignee_unassigned_open" in md)
check("Nam off_track=1", md["by_owner"]["Nam"]["off_track"] == 1)
check("by_epic present (not by_stage)", "by_epic" in md and "by_stage" not in md)
check("by_epic has Submission", "Submission" in md["by_epic"])
check("by_epic has Data & Platform", "Data & Platform" in md["by_epic"])
check("Disbursement in_progress=0", md["by_epic"]["Disbursement"]["in_progress"] == 0)
ua = m._render_unassigned_work_answer({"owner_unassigned_open": [
    {"key": "UW-6", "summary": "Untriaged funnel monitor", "status": "To Do", "assignee": "Unassigned", "owner": "Unassigned", "stage": "crosscut", "due": None}
]})
check("unassigned answer lists key", "UW-6" in ua and "Untriaged funnel monitor" in ua)
_old_all = jc.all_open_issues
jc.all_open_issues = lambda: list(_ISSUES) + [{
    "key": "UW-6", "summary": "Untriaged funnel monitor", "status": "To Do",
    "assignee": "Unassigned", "owner": "Unassigned", "stage": "crosscut",
    "epic": "Data & Platform", "due": None, "labels": ["stage-crosscut"],
    "type": "Task", "blocked_by": None, "blocks": None,
}]
ru = m.handler({"message": "what are those open tasks without assignee"}, None)
check("unassigned handler lists details", ru.get("intent") == "oversight" and "UW-6" in ru.get("answer", "") and "Untriaged funnel monitor" in ru.get("answer", ""))
jc.all_open_issues = _old_all

ro = m.handler({"message": "/jira what is critical or off track right now?"}, None)
ans = ro.get("answer", "")
check("offtrack deterministic", ro.get("intent") == "oversight" and "Critical / off-track snapshot" in ans)
check("offtrack no overloaded owners section", "overloaded" not in ans.lower() and "owner-load" not in ans.lower())
check("offtrack no epic-level blanks", "Epic-level view" not in ans and "Completion" not in ans)
check("offtrack uses Disbursement label", "Disbursement" in ans)

print("jira jql scoping + links:")
scoped = jc._scope_jql("statusCategory != Done ORDER BY due ASC")
check("project scope keeps ORDER BY outside parentheses", scoped == 'project = "UW" AND (statusCategory != Done) ORDER BY due ASC')
scoped2 = jc._scope_jql('statusCategory != Done AND labels = "blocked" ORDER BY due ASC')
check("complex scope keeps ORDER BY outside parentheses", scoped2 == 'project = "UW" AND (statusCategory != Done AND labels = "blocked") ORDER BY due ASC')
linked = jc.link_issue_keys("Opened UW-159 and https://x.atlassian.net/browse/UW-160 and [UW-161](x).")
check("bare issue linked", "[UW-159](https://x.atlassian.net/browse/UW-159)" in linked)
check("URL issue not double-linked", "browse/[UW-160]" not in linked)
check("markdown issue not double-linked", "[[UW-161]" not in linked)

print("epic parsing (real jira_client only):")
if hasattr(jc, "_epic_from_parent"):
    e = jc._epic_from_parent({"parent": {"key": "UW-1",
                              "fields": {"summary": "Submission", "issuetype": {"name": "Epic"}}}})
    check("epic from parent = Submission", e == "Submission")
    check("no parent -> None", jc._epic_from_parent({}) is None)
else:
    print("  (skipped — stubbed jira_client)")

print("due-soon:")
soon = (date.today() + timedelta(days=2)).isoformat()
check("near is due_soon", bf._is_due_soon({"due": soon, "status": "To Do", "labels": []}))
check("overdue not due_soon", not bf._is_due_soon({"due": "2020-01-01", "status": "To Do", "labels": []}))

print("shaping:")
check("my_briefing open=2", bf.my_briefing()["counts"]["open"] == 2)
sp = bf.sprint_pulse()
check("open_total=5", sp["open_total"] == 5)
check("In Review counted", sp["by_status"].get("In Review") == 1)
check("workload Rino=2", sp["workload_by_owner"].get("Rino") == 2)

print("/funnel")
import csv
from collections import defaultdict
import funnel_metrics as fm
check("6 months", len(fm.rows()) == 6)
check("sub rate", fm.rows()[0]["submission_rate_pct"] == round(100 * 240 / 750, 1))
check("latest 2026-05", fm.summary()["latest_month"] == "2026-05")
latest = fm.rows()[-1]
check("latest traffic from CSV = 800", latest["traffic"] == 800)
check("latest submission from CSV = 216", latest["submission"] == 216)
check("latest approval from CSV = 24", latest["approval"] == 24)
check("latest completion from CSV = 23", latest["completion"] == 23)
rank = {"traffic": 1, "submitted": 2, "approved": 3, "completed": 4}
by_day = defaultdict(lambda: [0, 0, 0, 0])
approval_drop_reasons = defaultdict(int)
with open(os.path.join(ROOT, "data", "funnel_synthetic.csv"), newline="", encoding="utf-8") as fcsv:
    for row in csv.DictReader(fcsv):
        if not row["entered_date"].startswith("2026-05"):
            continue
        sr = rank[row["final_stage"]]
        day = row["entered_date"]
        by_day[day][0] += 1
        if sr >= 2:
            by_day[day][1] += 1
        if sr >= 3:
            by_day[day][2] += 1
        if sr == 4:
            by_day[day][3] += 1
        if sr == 2:
            approval_drop_reasons[row["drop_reason"]] += 1
daily_totals = [sum(vals[i] for vals in by_day.values()) for i in range(4)]
check("daily sums reconcile to monthly", daily_totals == [800, 216, 24, 23])
check("all May calendar days populated", len(by_day) == 31)
check("approval drop reasons sum to submitted-approved", sum(approval_drop_reasons.values()) == 216 - 24)
rm = m.handler({"message": "show me the funnel metrics"}, None)
check("metrics intent", rm.get("intent") == "metrics")
check("metrics table", "Traffic" in rm.get("answer", ""))

print("write (create under Epic + stage-owner default):")
_cap = {}
jc.create_issue = lambda **k: (_cap.update(create=k) or {"key": "UW-99", "url": "u", "labels": []})
jc.assign_issue = lambda key, assignee_id=None, owner=None: (
    _cap.update(assign={"key": key, "assignee_id": assignee_id, "owner": owner})
    or {"key": key, "assigned_real": bool(assignee_id), "owner_label": ("owner-" + owner.lower()) if owner else None})
jc.find_assignable_user = lambda q, key=None: ({"accountId": "acc-1", "displayName": "Mai N."}
                                              if "mai" in q.lower() else None)
jc.myself = lambda: {"accountId": "me-1", "displayName": "You"}
jc.find_epic = lambda name, key=None: "UW-EPIC" if name else None

rc = m.handler({"message": "/jira create a ticket to pre-fill KYC"}, None)
check("create success", rc.get("status") == "success")
check("create intent", rc.get("intent") == "create")
check("created", _cap.get("create") is not None)
check("no priority arg", "priority" not in _cap.get("create", {}))
check("defaulted to stage owner when no assignee named", _cap["create"].get("owner") in {"Linh", "Mai"} and _cap["create"].get("assignee_id") != "me-1")

k, o = m.parse_assign("assign UW-23 to Mai")
check("parse key", k == "UW-23")
check("parse owner", o == "Mai")
ra = m.handler({"message": "/jira assign UW-23 to Mai"}, None)
check("assign intent", ra.get("intent") == "assign")
check("real assignee", _cap["assign"]["assignee_id"] == "acc-1")

print("anomaly + OKR target detection (real data):")
an = fm.anomalies()
check("MoM anomaly = approval", [a["stage"] for a in an] == ["approval"])
check("approval drop >= 3pp", an[0]["delta_pp"] <= -3)
tm = {x["stage"] for x in fm.target_misses()}
check("target_misses = submission + approval", tm == {"submission", "approval"})

print("metrics surfaces drop + target gap:")
rmet = m.handler({"message": "show me the funnel metrics"}, None)
check("metrics intent", rmet.get("intent") == "metrics")
check("metrics answer mentions target", "target" in rmet.get("answer", "").lower())
check("metrics answer includes MoM columns", "MoM Abs" in rmet.get("answer", "") and "MoM Pct" in rmet.get("answer", ""))
rtop = m.handler({"message": "why is approval the top risk?"}, None)
check("top-risk question intent", rtop.get("intent") == "metrics")
check("top-risk answer concise", "Approval is the top risk" in rtop.get("answer", ""))
check("impact ranking present", bool(rmet["result"].get("impact_ranking", {}).get("ranking")))
check("approval value at risk", any(x.get("stage") == "approval" and x.get("estimated_value_at_risk_vnd") for x in rmet["result"].get("impact_ranking", {}).get("ranking", [])))

print("analyst routing (SQL slices):")
import sql_analyst as sa
check("by drop reason -> analyst", m.route("break May down by drop reason") == "analyst")
check("approval drop down by reason -> analyst", m.route("break May approval drop down by reason") == "analyst")
sql_dr, tmpl_dr = sa.template_sql("break May approval drop down by reason")
check("approval drop by reason uses drop template", tmpl_dr == "approval_drop_reason_breakdown")
check("approval drop by reason SQL scopes dropped submitted rows", "WHERE stage_rank = 2" in sql_dr and "stage_drop_total" in sql_dr)
check("by product -> analyst", m.route("show May by product") == "analyst")
check("plain metrics stays metrics", m.route("show me the funnel metrics") == "metrics")
check("explicit MoM comparison -> metrics", m.route("can you do MoM comparison between March and April and see what's critical?") == "metrics")

print("explicit month comparison:")
cmp = m.handler({"message": "can you do MoM comparison between March and April and see what's critical?"}, None)
check("comparison intent", cmp.get("intent") == "metrics")
check("comparison uses requested months", "2026-03 → 2026-04" in cmp.get("answer", ""))
check("comparison does not answer latest May only", "This comparison answers the requested months only" in cmp.get("answer", ""))
check("comparison flags submission target", "Submission" in cmp.get("answer", "") and "28.0%" in cmp.get("answer", "") and "30.0% target" in cmp.get("answer", ""))
rapr = m.handler({"message": "show me the funnel metrics in April"}, None)
check("April metrics intent", rapr.get("intent") == "metrics")
check("April metrics cut off May table", "2026-05" not in rapr.get("answer", "") and "2026-04" in rapr.get("answer", ""))
check("April recovery priority is submission", "Top recovery priority:** Submission" in rapr.get("answer", "") or "top recovery priority: Submission" in rapr.get("answer", ""))
rapr2 = m.handler({"message": "can you cutoff May and show what's recovery priority in April?"}, None)
check("April top-risk scoped", "As of **2026-04**" in rapr2.get("answer", "") and "Submission is the top risk" in rapr2.get("answer", ""))
check("April top-risk does not use May diagnostic suggestion", "break May" not in rapr2.get("answer", ""))
check("create-ticket mixed intent routes create", m.route("I'd like to investigate traffic drop in May also, create a ticket for this") == "create")
dbh = m.handler({"message": "how do I query the database?"}, None)
check("database help includes schema", dbh.get("intent") == "help" and "funnel" in dbh.get("answer", "") and "stage_rank" in dbh.get("answer", ""))
ep = m.handler({"message": "who's the owner of each epic?"}, None)
check("epic owner routes oversight", ep.get("intent") == "oversight")
check("epic owner uses effective owner", "operational owner" in ep.get("answer", "") and "Submission" in ep.get("answer", ""))

print("weekly meeting pack:")
w = m.handler({"message": "summarize everything for weekly meeting"}, None)
check("weekly intent", w.get("intent") == "weekly")
check("weekly answer agenda", "agenda" in w.get("answer", "").lower())
check("weekly confluence context", "recent_confluence_pages" in w.get("result", {}))
check("weekly blocked context", "blocked by certificate approval" in w.get("answer", ""))
filtered_pages = bf._filter_context_pages([
    {"title": "Weekly Funnel Agent Summary - 2026-06-14", "body": "self"},
    {"title": "Decision log - Funnel", "body": "decision"},
])
check("weekly context excludes self-generated pages", [p["title"] for p in filtered_pages] == ["Decision log - Funnel"])

print("teams reminder:")
teams = m.handler({"message": "/teams send off-track reminder"}, None)
check("teams intent", teams.get("intent") == "teams")
check("teams previews when webhook missing", "did not post" in teams.get("answer", "") and "UW-1" in teams.get("answer", ""))

print("chat UI version:")
with open(os.path.join(ROOT, "chat.html"), encoding="utf-8") as fh:
    chat_html = fh.read()
check("chat header has UI version", "UI v27" in chat_html)
check("chat JS has one UI_VERSION const", chat_html.count("const UI_VERSION") == 1)

check("chat has demo side panel", "Demo flow" in chat_html and "demo-step" in chat_html)
check("chat has sidebar toggle", "sidebar-toggle" in chat_html and "Hide demo panel" in chat_html and "setSidebar" in chat_html)
check("sidebar collapsed mode expands chat", "sidebar-collapsed" in chat_html and "grid-template-columns: minmax(0, 1fr)" in chat_html)
check("chat wraps tables", "table-scroll" in chat_html and "renderMarkdown" in chat_html)
check("footer minimal", "Powered by GreenNode AgentBase + MaaS." in chat_html and "Synthetic workspace data" not in chat_html)
check("pitch tab is product FAQ not demo guide", "FAQ" in chat_html and "What problem does Funnel Agent solve?" in chat_html and "Demo storyline" not in chat_html)

print("confluence markdown conversion:")
storage = cf.markdown_to_storage("""# Weekly Brief

**Date:** 2026-06-14

1. **Approval risk**

* **Signal:** below target

| Rank | Stage |
|---:|---|
| 1 | Approval |
""")
check("inline bold rendered", "<strong>Date:</strong>" in storage)
check("star bullet rendered", "<li><strong>Signal:</strong> below target</li>" in storage)
check("markdown table rendered", "<table>" in storage and "<th>Rank</th>" in storage)


print("confluence storage rendering:")
storage = cf.markdown_to_storage("""# Weekly Funnel Review Brief

**Date:** 2026-06-14 | **Scenario:** Demo funnel

1. **Approval Rate Decline**
   * **Signal:** 11.1% actual vs target.

| Metric | Value |
|---|---|
| **Approval** | `11.1%` |
""")
check("bold converted", "<strong>Date:</strong>" in storage and "**Date:**" not in storage)
check("star bullet converted", "<li><strong>Signal:</strong>" in storage)
check("table converted", "<table>" in storage and "<th>Metric</th>" in storage)

print("flag dedup (MoM drop + target miss -> one task per stage):")
jc.all_open_issues = lambda: [_mk("UW-7", "Approval analytics", "To Do", "Dat Nguyen", "approval", "2026-12-30"),
                              _mk("UW-8", "Submission lineage", "To Do", "Linh", "submission", "2026-12-30")]
_capf = []
jc.create_issue = lambda **k: (_capf.append(k) or {"key": "UW-%d" % (len(_capf) + 100), "url": "u"})
jc.find_assignable_user = lambda q, key=None: {"accountId": "acc-" + q.split()[0].lower(), "displayName": q}
jc.find_epic = lambda name, key=None: "UW-EPIC"
rf = m.handler({"message": "/jira flag the drops and assign owners to investigate"}, None)
check("flag intent", rf.get("intent") == "flag")
check("flagged approval + submission (deduped)", set(rf["result"]["stages"]) == {"approval", "submission"})
check("one task per stage (2 total)", len(_capf) == 2)
check("approval task assigned to its owner", any(c.get("stage") == "approval" and c.get("assignee_id") == "acc-dat" for c in _capf))

print("v10 bug regressions:")
r_apr = m.handler({"message": "show me the funnel metrics in April"}, None)
check("April metrics is month-scoped", r_apr.get("intent") == "metrics" and "Month-scoped view: treating 2026-04" in r_apr.get("answer", ""))
check("April metrics does not lead with May approval risk", "108.1M VND" not in r_apr.get("answer", ""))
r_cut = m.handler({"message": "can you cutoff May and show what's recovery priority in April?"}, None)
check("cutoff May uses April", "As of **2026-04**" in r_cut.get("answer", ""))
check("April top risk is submission", "Submission is the top risk" in r_cut.get("answer", ""))
check("create-ticket with diagnostic words routes create", m.route("I'd like to investigate traffic drop in May also, create a ticket for this") == "create")
rd = m.handler({"message": "how do I query the database?"}, None)
check("database help mentions funnel view", rd.get("intent") == "help" and "`funnel` view" in rd.get("answer", ""))
reo = m.handler({"message": "who's the owner of each epic?"}, None)
check("epic owner answer distinguishes operational owner", "operational stage owner" in reo.get("answer", ""))

print("v27 model + natural funnel + external commands:")
check("slash model routes model", m.route("/model") == "model")
mdl = m.handler({"message": "/model"}, None)
check("model handler works", mdl.get("intent") == "model" and "Chat model" in mdl.get("answer", ""))
check("/funnel data drilldown routes analyst", m.route("/funnel break May approval drop down by reason") == "analyst")
rdrop = m.handler({"message": "/funnel break May approval drop down by reason"}, None)
check("/funnel drop reason works", rdrop.get("intent") == "analyst" and ("Submission → Approval reconciliation" in rdrop.get("answer", "") or "application-level dataset is not available" in rdrop.get("answer", "")))
check("drop reason includes audit sql", "Audit SQL" in rdrop.get("answer", "") or "application-level dataset is not available" in rdrop.get("answer", ""))
# Regression: this used to fall through to the full metrics table instead of answering the history/outcome question.
rhist = m.handler({"message": "what has been done in March to improve the approval rate? or if it's been done at all"}, None)
check("stage history question answers with caveat", rhist.get("intent") == "metrics" and "closed-loop outcome tracking" in rhist.get("answer", ""))
# Regression: broad Jira task list questions should not dump raw JSON.
rtasks = m.handler({"message": "/jira give me all the tasks along with assignee and due date and status"}, None)
check("all tasks deterministic table", rtasks.get("intent") == "oversight" and "| Key | Summary | Assignee |" in rtasks.get("answer", "") and "Data JSON" not in rtasks.get("answer", ""))

print("v23 seed/storyboard cleanup:")
seed_text = open(os.path.join(ROOT, "scripts", "seed_atlassian.py"), encoding="utf-8").read()
check("monthly Jira seeds present", "month-2026-03" in seed_text and "month-2026-04" in seed_text and "month-2026-05" in seed_text)
check("monthly Confluence seeds present", "Monthly Funnel Review - 2026-03" in seed_text and "Decision Log - Submission Instrumentation - 2026-04" in seed_text)
check("Teams notification policy seeded", "Teams notification policy" in seed_text and "09:00 digest" in seed_text and "17:00 reminder" in seed_text)
check("old docs removed", not os.path.exists(os.path.join(ROOT, "AGENT_SPEC.md")) and not os.path.exists(os.path.join(ROOT, "PIVOT_SPEC.md")) and not os.path.exists(os.path.join(ROOT, "HOW_TO_USE_WATCHTOWER.md")))
story_text = open(os.path.join(ROOT, "DEMO_VIDEO_STORYBOARD.md"), encoding="utf-8").read()
check("storyboard includes cross-system workflow", "Detect -> Diagnose -> Assign -> Summarize -> Notify" in story_text and "Teams" in story_text and "Confluence" in story_text and "Jira" in story_text)

print("prefix routing guards:")
np = m.handler({"message": "flag the drops and assign owners to investigate"}, None)
check("non-prefixed write requires prefix", np.get("result", {}).get("prefix_required") is True and "/jira" in np.get("answer", ""))
rn = m.handler({"message": "show me the funnel metrics"}, None)
check("non-prefixed read-only has no routing warning", "Routing note" not in rn.get("answer", ""))
rp = m.handler({"message": "/funnel show me the funnel metrics"}, None)
check("optional /funnel read-only has no routing warning", "Routing note" not in rp.get("answer", ""))
check("funnel metrics includes audit query", "Audit query" in rp.get("answer", ""))
clar = m.handler({"message": "why did it drop"}, None)
check("ambiguous drop asks clarification", clar.get("result", {}).get("clarification_required") is True and "Which funnel transition" in clar.get("answer", ""))


print("capability help guard:")
rth = m.handler({"message": "/teams what are teams function"}, None)
check("teams capability question does not post", rth.get("intent") == "help" and "Teams" in rth.get("answer", "") and "Posted" not in rth.get("answer", ""))
rjh = m.handler({"message": "/jira what are jira function"}, None)
check("jira capability question routes help", rjh.get("intent") == "help" and "Jira" in rjh.get("answer", ""))
rch = m.handler({"message": "/confluence what confluence functions?"}, None)
check("confluence capability question routes help", rch.get("intent") == "help" and "Confluence" in rch.get("answer", ""))

print(f"\n{PASS} passed, {FAIL} failed")


def test_offline_suite_passed():
    assert FAIL == 0


if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
