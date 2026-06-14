"""Offline tests for Funnel Watchtower — no network, no LLM, no Atlassian.

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
                  ATLASSIAN_EMAIL="x@y.z", ATLASSIAN_TOKEN="t" * 192, ALLOW_WRITES="true")
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("LLM_BASE_URL", None)

import jira_client as jc
import confluence_client as cf
import main as m

_EPIC = {"traffic": "Traffic", "submission": "Submission", "approval": "Approval",
         "completion": "Completion", "crosscut": "Data & Platform"}


def _mk(key, summary, status, owner, stage, due, labels=None, blocked_by=None, blocks=None):
    """Mirror jira_client._brief: simple model, epic = the stage's Epic name."""
    labels = (labels or []) + [f"owner-{owner.lower()}", f"stage-{stage}"]
    return {"key": key, "summary": summary, "status": status, "assignee": "Rino Tran",
            "owner": owner, "stage": stage, "epic": _EPIC.get(stage), "due": due,
            "labels": labels, "type": "Task", "blocked_by": blocked_by, "blocks": blocks}


_ISSUES = [
    _mk("UW-1", "Renew TLS certs", "To Do", "Nam", "completion", "2026-01-10", ["blocked", "infra"],
        blocked_by="certificate approval", blocks="secure completion webhook"),
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
check("assign", m.route("assign KAN-23 to Mai") == "assign")
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
check("VI->oversight", m.route("ai dang lam gi, co gi tre khong?") == "oversight")
check("gibberish->help", m.route("zzz qwerty") == "help")

print("handler:")
for q, intent in [("funnel overview", "oversight"), ("what's on my plate?", "briefing"),
                  ("how is the sprint going?", "sprint"), ("what did we decide?", "knowledge"),
                  ("draft my standup", "standup"), ("summarize everything for weekly meeting", "weekly"), ("hello", "help")]:
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
check("Nam off_track=1", md["by_owner"]["Nam"]["off_track"] == 1)
check("by_epic present (not by_stage)", "by_epic" in md and "by_stage" not in md)
check("by_epic has Submission", "Submission" in md["by_epic"])
check("by_epic has Data & Platform", "Data & Platform" in md["by_epic"])
check("Completion in_progress=0", md["by_epic"]["Completion"]["in_progress"] == 0)

print("epic parsing (real jira_client only):")
if hasattr(jc, "_epic_from_parent"):
    e = jc._epic_from_parent({"parent": {"key": "KAN-1",
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

print("metrics:")
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

print("write (create under Epic + assign-to-self):")
_cap = {}
jc.create_issue = lambda **k: (_cap.update(create=k) or {"key": "UW-99", "url": "u", "labels": []})
jc.assign_issue = lambda key, assignee_id=None, owner=None: (
    _cap.update(assign={"key": key, "assignee_id": assignee_id, "owner": owner})
    or {"key": key, "assigned_real": bool(assignee_id), "owner_label": ("owner-" + owner.lower()) if owner else None})
jc.find_assignable_user = lambda q, key=None: ({"accountId": "acc-1", "displayName": "Mai N."}
                                              if "mai" in q.lower() else None)
jc.myself = lambda: {"accountId": "me-1", "displayName": "You"}
jc.find_epic = lambda name, key=None: "KAN-EPIC" if name else None

rc = m.handler({"message": "create a ticket to pre-fill KYC"}, None)
check("create success", rc.get("status") == "success")
check("create intent", rc.get("intent") == "create")
check("created", _cap.get("create") is not None)
check("no priority arg", "priority" not in _cap.get("create", {}))
check("assigned to self by default", _cap["create"].get("assignee_id") == "me-1")

k, o = m.parse_assign("assign KAN-23 to Mai")
check("parse key", k == "KAN-23")
check("parse owner", o == "Mai")
ra = m.handler({"message": "assign KAN-23 to Mai"}, None)
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
check("impact ranking present", bool(rmet["result"].get("impact_ranking", {}).get("ranking")))
check("approval value at risk", any(x.get("stage") == "approval" and x.get("estimated_value_at_risk_vnd") for x in rmet["result"].get("impact_ranking", {}).get("ranking", [])))

print("analyst routing (SQL slices):")
check("by drop reason -> analyst", m.route("break May down by drop reason") == "analyst")
check("by product -> analyst", m.route("show May by product") == "analyst")
check("plain metrics stays metrics", m.route("show me the funnel metrics") == "metrics")

print("weekly meeting pack:")
w = m.handler({"message": "summarize everything for weekly meeting"}, None)
check("weekly intent", w.get("intent") == "weekly")
check("weekly answer agenda", "agenda" in w.get("answer", "").lower())
check("weekly confluence context", "recent_confluence_pages" in w.get("result", {}))
check("weekly blocked context", "blocked by certificate approval" in w.get("answer", ""))

print("flag dedup (MoM drop + target miss -> one task per stage):")
jc.all_open_issues = lambda: [_mk("UW-7", "Approval analytics", "To Do", "Dat Nguyen", "approval", "2026-12-30"),
                              _mk("UW-8", "Submission lineage", "To Do", "Linh", "submission", "2026-12-30")]
_capf = []
jc.create_issue = lambda **k: (_capf.append(k) or {"key": "UW-%d" % (len(_capf) + 100), "url": "u"})
jc.find_assignable_user = lambda q, key=None: {"accountId": "acc-" + q.split()[0].lower(), "displayName": q}
jc.find_epic = lambda name, key=None: "KAN-EPIC"
rf = m.handler({"message": "flag the drops and assign owners to investigate"}, None)
check("flag intent", rf.get("intent") == "flag")
check("flagged approval + submission (deduped)", set(rf["result"]["stages"]) == {"approval", "submission"})
check("one task per stage (2 total)", len(_capf) == 2)
check("approval task assigned to its owner", any(c.get("stage") == "approval" and c.get("assignee_id") == "acc-dat" for c in _capf))

print(f"\n{PASS} passed, {FAIL} failed")


def test_offline_suite_passed():
    assert FAIL == 0


if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
