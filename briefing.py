"""Briefing composition — Funnel Watchtower, Team UW.

Deterministic data shaping from Jira/Confluence; LLM (report.llm_chat) narrates.
Every function returns structured JSON the LLM can quote but not contradict.
The centerpiece is manager_digest() — the lending lead's oversight view.
"""
import confluence_client as cf
import jira_client as jc


def jc_today() -> str:
    from datetime import date
    return date.today().isoformat()


def _is_blocked(i: dict) -> bool:
    return "blocked" in [l.lower() for l in i["labels"]] or (i["status"] or "").lower() == "blocked"


def _is_overdue(i: dict) -> bool:
    return bool(i["due"]) and i["due"] < jc_today()


def _is_critical(i: dict) -> bool:
    return (i["priority"] or "").lower() in jc.CRITICAL_PRIORITIES


def manager_digest() -> dict:
    """Lending lead's oversight view: who owns what, on/off track, what's critical,
    broken down by funnel stage. This is the line-manager centerpiece."""
    open_issues = jc.all_open_issues()
    done = jc.done_issues()

    by_owner: dict = {}
    by_stage: dict = {}
    for i in open_issues:
        owner = i["owner"]
        stage = i["stage"] or "unassigned-stage"
        by_owner.setdefault(owner, {"count": 0, "critical": 0, "off_track": 0})
        by_owner[owner]["count"] += 1
        if _is_critical(i):
            by_owner[owner]["critical"] += 1
        if _is_overdue(i) or _is_blocked(i):
            by_owner[owner]["off_track"] += 1
        by_stage.setdefault(stage, {"open": 0, "in_progress": 0})
        by_stage[stage]["open"] += 1
        if (i["status"] or "").lower() == "in progress":
            by_stage[stage]["in_progress"] += 1

    off_track = [i for i in open_issues if _is_overdue(i) or _is_blocked(i)]
    critical = [i for i in open_issues if _is_critical(i)]
    # the items a lead must look at first: critical AND off track
    needs_attention = [i for i in open_issues if _is_critical(i) and (_is_overdue(i) or _is_blocked(i))]

    return {
        "as_of": jc_today(),
        "totals": {"open": len(open_issues), "done": len(done),
                   "critical_open": len(critical), "off_track": len(off_track)},
        "needs_attention_now": needs_attention,
        "off_track": off_track,
        "critical_open": critical,
        "by_owner": by_owner,
        "by_stage": by_stage,
        "recently_completed": done[:5],
        "note": "needs_attention_now = critical AND (overdue or blocked); escalate these first.",
    }


def my_briefing() -> dict:
    """Everything 'on my plate': open issues ranked, blockers, overdue."""
    mine = jc.my_open_issues()
    return {
        "my_open_issues": mine,
        "my_blocked": [i for i in mine if _is_blocked(i)],
        "my_overdue": [i for i in mine if _is_overdue(i)],
        "counts": {"open": len(mine)},
    }


def sprint_pulse() -> dict:
    """Whole-team view: status mix, blockers, overdue, load per owner."""
    open_issues = jc.all_open_issues()
    done = jc.done_issues()
    by_status: dict = {}
    by_owner: dict = {}
    for i in open_issues:
        by_status[i["status"]] = by_status.get(i["status"], 0) + 1
        by_owner[i["owner"]] = by_owner.get(i["owner"], 0) + 1
    return {
        "open_total": len(open_issues),
        "done_total": len(done),
        "by_status": by_status,
        "workload_by_owner": by_owner,
        "blocked": jc.blocked_issues(),
        "overdue": jc.overdue_issues(),
        "recently_done": done[:5],
    }


def knowledge(query: str) -> dict:
    """Confluence lookup: top pages + content for the LLM to answer from."""
    pages = cf.search_pages(query)
    return {
        "query": query,
        "pages_found": len(pages),
        "pages": pages,
        "note": "answer ONLY from these pages; cite the page title and url",
    }


def standup_draft() -> dict:
    """Material for a yesterday/today/blockers standup message."""
    mine = jc.my_open_issues()
    done = jc.done_issues()[:5]
    return {
        "recently_done_by_team": done,
        "my_in_progress": [i for i in mine if (i["status"] or "").lower() == "in progress"],
        "my_todo": [i for i in mine if (i["status"] or "").lower() in ("to do", "open", "backlog")],
        "my_blockers": [i for i in mine if _is_blocked(i)],
    }
