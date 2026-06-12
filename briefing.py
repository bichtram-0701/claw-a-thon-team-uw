"""Briefing composition — Sprint Sidekick, Team UW.

Deterministic data shaping from Jira/Confluence; LLM (report.llm_chat) narrates.
Every function returns structured JSON the LLM can quote but not contradict.
"""
import confluence_client as cf
import jira_client as jc


def my_briefing() -> dict:
    """Everything 'on my plate': open issues ranked, blockers, overdue."""
    mine = jc.my_open_issues()
    return {
        "my_open_issues": mine,
        "my_blocked": [i for i in mine if "blocked" in [l.lower() for l in i["labels"]]
                       or (i["status"] or "").lower() == "blocked"],
        "my_overdue": [i for i in mine if i["due"] and i["due"] < jc_today()],
        "counts": {"open": len(mine)},
    }


def jc_today() -> str:
    from datetime import date
    return date.today().isoformat()


def sprint_pulse() -> dict:
    """Whole-team view: status mix, blockers, overdue, load per person."""
    open_issues = jc.all_open_issues()
    done = jc.done_issues()
    by_status: dict = {}
    by_assignee: dict = {}
    for i in open_issues:
        by_status[i["status"]] = by_status.get(i["status"], 0) + 1
        by_assignee[i["assignee"]] = by_assignee.get(i["assignee"], 0) + 1
    return {
        "open_total": len(open_issues),
        "done_total": len(done),
        "by_status": by_status,
        "workload_by_assignee": by_assignee,
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
    done = [i for i in jc.done_issues() if i["assignee"] != "Unassigned"][:5]
    return {
        "recently_done_by_team": done,
        "my_in_progress": [i for i in mine if (i["status"] or "").lower() == "in progress"],
        "my_todo": [i for i in mine if (i["status"] or "").lower() in ("to do", "open", "backlog")],
        "my_blockers": [i for i in mine if "blocked" in [l.lower() for l in i["labels"]]
                        or (i["status"] or "").lower() == "blocked"],
    }
