"""Offline tests for Funnel Watchtower — no network, no LLM, no Atlassian.

The dev sandbox can't reach Atlassian or MaaS, so we stub the Jira/Confluence
clients with synthetic fixtures and force the LLM offline. This exercises the
real code paths that matter without credentials:
  - intent routing (keywords)
  - manager_digest (the LM oversight centerpiece) + the other shapers
  - the handler end-to-end with the deterministic (LLM-down) fallback

Run:  python tests/test_offline.py     (from repo root)
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# --- make the import of main.py work without the GreenNode SDK installed -----
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

# --- credentials present (so handler doesn't short-circuit) but LLM absent ----
os.environ.update(ATLASSIAN_SITE="https://x.atlassian.net",
                  ATLASSIAN_EMAIL="x@y.z", ATLASSIAN_TOKEN="t" * 192)
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("LLM_BASE_URL", None)

import jira_client as jc       # noqa: E402
import confluence_client as cf  # noqa: E402
import main as m               # noqa: E402


# --------------------------------------------------------------- fixtures ----
# Mirrors the shape jira_client._brief produces (owner/stage parsed from labels).
def _mk(key, summary, status, owner, stage, prio, due, labels=None):
    labels = (labels or []) + [f"owner-{owner.lower()}", f"stage-{stage}"]
    return {"key": key, "summary": summary, "status": status, "assignee": "Rino Tran",
            "owner": owner, "stage": stage, "priority": prio, "due": due,
            "labels": labels, "type": "Story"}


_ISSUES = [
    # critical AND off track (overdue + blocked) -> must be needs_attention_now
    _mk("UW-1", "Renew TLS certs for partner disbursement API", "To Do", "Nam", "disbursed",
        "Highest", "2026-06-11", ["blocked", "infra"]),
    # critical, in progress, on track
    _mk("UW-2", "Reduce web docs-upload abandonment", "In Progress", "Linh", "docs",
        "Highest", "2026-06-15"),
    # blocked (off track) but not critical
    _mk("UW-3", "Migrate risk-score batch job", "To Do", "Rino", "crosscut",
        "High", "2026-06-15", ["blocked"]),
    # Rino's own, on track
    _mk("UW-4", "Instrument funnel events end-to-end", "In Progress", "Rino", "crosscut",
        "High", "2026-06-16"),
    _mk("UW-5", "A/B test simplified application form", "To Do", "Mai", "applied",
        "Medium", "2026-06-20"),
]
_DONE = [
    _mk("UW-9", "Baseline funnel conversion report", "Done", "Rino", "crosscut",
        "Medium", "2026-06-10"),
]


def _mine():
    return [i for i in _ISSUES if i["owner"] == "Rino" and i["status"] != "Done"]


jc.my_open_issues = _mine
jc.all_open_issues = lambda: list(_ISSUES)
jc.done_issues = lambda: list(_DONE)
jc.blocked_issues = lambda: [i for i in _ISSUES if "blocked" in i["labels"]]
jc.overdue_issues = lambda: [i for i in _ISSUES if i["due"] < "2026-06-13"]
cf.search_pages = lambda q, limit=3: [
    {"title": "Decision log — Funnel", "url": "https://x/wiki/1",
     "excerpt": "docs-upload is the #1 priority", "body": "Decision: treat docs-upload as the top initiative."}
]

# ----------------------------------------------------------------- tests -----
PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


print("routing:")
check("overview -> oversight", m.route("give me the funnel overview") == "oversight")
check("who working -> oversight", m.route("who is working on what?") == "oversight")
check("critical/off track -> oversight", m.route("what's critical or off track?") == "oversight")
check("plate -> briefing", m.route("what's on my plate?") == "briefing")
check("sprint -> sprint", m.route("how is the sprint going?") == "sprint")
check("decide -> knowledge", m.route("what did we decide about docs-upload?") == "knowledge")
check("standup -> standup", m.route("draft my standup") == "standup")
check("VI oversight -> oversight", m.route("ai dang lam gi, co gi tre khong?") == "oversight")
check("gibberish -> help (LLM offline)", m.route("zzz qwerty") == "help")

print("handler (LLM offline -> deterministic fallback):")
for q, intent in [("give me the funnel overview", "oversight"),
                  ("what's on my plate?", "briefing"),
                  ("how is the sprint going?", "sprint"),
                  ("what did we decide about docs-upload?", "knowledge"),
                  ("draft my standup", "standup"),
                  ("hello", "help")]:
    r = m.handler({"message": q}, None)
    check(f"{intent}: status success", r.get("status") == "success")
    check(f"{intent}: correct intent", r.get("intent") == intent)
    check(f"{intent}: non-empty answer", bool(r.get("answer")))

print("manager_digest (LM oversight centerpiece):")
import briefing as bf  # noqa: E402
md = bf.manager_digest()
check("totals open=5", md["totals"]["open"] == 5)
check("totals critical_open=4", md["totals"]["critical_open"] == 4)
check("needs_attention = UW-1 & UW-3 (critical AND off track)",
      {i["key"] for i in md["needs_attention_now"]} == {"UW-1", "UW-3"})
check("off_track has UW-1 and UW-3", {i["key"] for i in md["off_track"]} == {"UW-1", "UW-3"})
check("by_owner tracks Nam off_track", md["by_owner"]["Nam"]["off_track"] == 1)
check("by_stage has docs", "docs" in md["by_stage"])
check("by_stage disbursed in_progress=0", md["by_stage"]["disbursed"]["in_progress"] == 0)

print("other shaping:")
b = bf.my_briefing()
check("my_briefing counts open=2 (Rino's)", b["counts"]["open"] == 2)
check("my_briefing finds blocked UW-3", any(i["key"] == "UW-3" for i in b["my_blocked"]))
sp = bf.sprint_pulse()
check("sprint_pulse open_total=5", sp["open_total"] == 5)
check("sprint_pulse workload by owner has Rino=2", sp["workload_by_owner"].get("Rino") == 2)
kn = bf.knowledge("docs-upload")
check("knowledge returns pages", kn["pages_found"] == 1)
su = bf.standup_draft()
check("standup has in-progress UW-4", any(i["key"] == "UW-4" for i in su["my_in_progress"]))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
