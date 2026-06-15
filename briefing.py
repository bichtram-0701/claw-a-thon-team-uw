"""Briefing composition — Funnel Watchtower, Team UW.

Deterministic data shaping from Jira/Confluence; the LLM narrates only from
this structured JSON. The centerpiece is manager_digest(): the business lead's
execution view, augmented with impact ranking and value-at-risk scoring.
"""
from __future__ import annotations

import confluence_client as cf
import funnel_metrics as fm
import impact as im
import jira_client as jc


def jc_today() -> str:
    from datetime import date
    return date.today().isoformat()


def _is_blocked(i: dict) -> bool:
    return "blocked" in [str(l).lower() for l in i.get("labels", [])] or (i.get("status") or "").lower() == "blocked"


def _is_overdue(i: dict) -> bool:
    return bool(i.get("due")) and i["due"] < jc_today()


def _is_due_soon(i: dict, days: int = 3) -> bool:
    """Open item due within `days` and not already overdue."""
    if not i.get("due") or _is_overdue(i):
        return False
    from datetime import date, timedelta
    return i["due"] <= (date.today() + timedelta(days=days)).isoformat()


def _blocker_note(i: dict) -> str | None:
    """Human-readable blocker context for a blocked issue, if available."""
    if not _is_blocked(i):
        return None
    blocked_by = i.get("blocked_by")
    blocks = i.get("blocks")
    if blocked_by and blocks:
        return f"blocked by {blocked_by}; blocks {blocks}"
    if blocked_by:
        return f"blocked by {blocked_by}"
    if blocks:
        return f"blocks {blocks}"
    return "blocked label present; blocker detail not specified in Jira"


def _open_done() -> tuple[list[dict], list[dict]]:
    return jc.all_open_issues(), jc.done_issues()


def stage_owners_from_issues(issues: list[dict]) -> dict:
    """Map each funnel stage -> most common operational owner.

    Unassigned investigation tickets should not override the seeded stage owner.
    We therefore ignore Unassigned values when at least one named owner exists
    for a stage, and only return Unassigned if no named owner exists at all.
    """
    from collections import Counter
    buckets: dict = {}
    for i in issues:
        st = i.get("stage")
        if st:
            buckets.setdefault(st, []).append(i.get("owner") or i.get("assignee") or "Unassigned")
    out = {}
    for st, owners in buckets.items():
        named = [o for o in owners if o and o != "Unassigned"]
        out[st] = Counter(named or owners).most_common(1)[0][0]
    return out


def stage_owners() -> dict:
    """Map each funnel stage -> the person who owns it."""
    return stage_owners_from_issues(jc.all_open_issues())


def manager_digest() -> dict:
    """Business lead's oversight view: ownership, off-track work, and ranked risks."""
    open_issues, done = _open_done()
    owners = stage_owners_from_issues(open_issues)

    by_owner: dict = {}
    by_epic: dict = {}
    for i in open_issues:
        owner = i.get("owner") or "Unassigned"
        epic = i.get("epic") or "Unsorted"   # Epic = funnel stage / project
        by_owner.setdefault(owner, {"count": 0, "off_track": 0})
        by_owner[owner]["count"] += 1
        if _is_overdue(i) or _is_blocked(i):
            by_owner[owner]["off_track"] += 1
        by_epic.setdefault(epic, {"open": 0, "in_progress": 0})
        by_epic[epic]["open"] += 1
        if (i.get("status") or "").lower() == "in progress":
            by_epic[epic]["in_progress"] += 1

    off_track = [i for i in open_issues if _is_overdue(i) or _is_blocked(i)]
    due_soon = [i for i in open_issues if _is_due_soon(i)]
    owner_unassigned = [
        i for i in open_issues
        if (i.get("owner") or i.get("assignee") or "Unassigned") == "Unassigned"
    ]
    assignee_unassigned = [
        i for i in open_issues
        if (i.get("assignee") or "Unassigned") == "Unassigned"
    ]

    return {
        "as_of": jc_today(),
        "totals": {"open": len(open_issues), "done": len(done),
                   "off_track": len(off_track), "due_soon": len(due_soon),
                   "owner_unassigned": len(owner_unassigned),
                   "assignee_unassigned": len(assignee_unassigned)},
        "needs_attention_now": off_track,
        "due_soon": due_soon,
        "owner_unassigned_open": owner_unassigned,
        "assignee_unassigned_open": assignee_unassigned,
        "by_owner": by_owner,
        "by_epic": by_epic,
        "stage_owners": owners,
        "impact_ranking": im.rank_stage_risks(open_issues, owners),
        "recently_completed": done[:5],
        "note": "needs_attention_now = overdue OR blocked. In this demo, blocked means a Jira label/status flag, not a workflow state; blocked_by/blocks explains the dependency when known. due_soon = due within 3 days. "
                "owner_unassigned_open lists open issues without a normalized owner; assignee_unassigned_open lists open issues without a real Jira assignee. "
                "by_epic groups initiatives by Epic (funnel stage / project). "
                "impact_ranking is deterministic: target gap + value at risk + Jira execution risk.",
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
    open_issues, done = _open_done()
    by_status: dict = {}
    by_owner: dict = {}
    for i in open_issues:
        by_status[i.get("status")] = by_status.get(i.get("status"), 0) + 1
        owner = i.get("owner") or "Unassigned"
        by_owner[owner] = by_owner.get(owner, 0) + 1
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
        "my_in_progress": [i for i in mine if (i.get("status") or "").lower() == "in progress"],
        "my_todo": [i for i in mine if (i.get("status") or "").lower() in ("to do", "open", "backlog")],
        "my_blockers": [i for i in mine if _is_blocked(i)],
    }


def _is_generated_weekly_page(page: dict) -> bool:
    title = str(page.get("title") or "").lower()
    return any(k in title for k in [
        "weekly funnel watchtower summary",
        "funnel watchtower weekly readout",
        "weekly funnel review brief",
    ])


def _filter_context_pages(pages: list[dict]) -> list[dict]:
    """Exclude pages generated by Watchtower so weekly notes do not cite themselves."""
    if pages and pages[0].get("error"):
        return pages
    return [p for p in pages if not _is_generated_weekly_page(p)]


def _clean_snippet(text: str, limit: int = 180) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return cut + "..."


def _safe_recent_pages(limit: int = 8) -> list[dict]:
    try:
        return _filter_context_pages(cf.recent_pages(limit=limit, with_body=True))
    except Exception as e:  # noqa: BLE001
        return [{"error": str(e)[:160]}]


def _safe_decisions() -> list[dict]:
    try:
        return _filter_context_pages(cf.search_pages("decision funnel approval submission completion weekly meeting", limit=8))
    except Exception as e:  # noqa: BLE001
        return [{"error": str(e)[:160]}]


def weekly_meeting_pack() -> dict:
    """All deterministic material needed for a weekly LM meeting summary."""
    digest = manager_digest()
    pulse = sprint_pulse()
    metric_summary = fm.summary()
    return {
        "as_of": jc_today(),
        "meeting_type": "weekly_funnel_review",
        "funnel_metrics": metric_summary,
        "impact_ranking": digest.get("impact_ranking"),
        "execution_digest": digest,
        "sprint_pulse": pulse,
        "recently_completed": digest.get("recently_completed", []),
        "confluence_decisions": _safe_decisions(),
        "recent_confluence_pages": _safe_recent_pages(),
        "recommended_agenda": [
            "Review target misses and estimated value at risk",
            "Confirm owner and ETA for the top recovery item",
            "Review blockers and overdue work",
            "Check completed initiatives and whether metrics moved",
            "Record decisions and next recovery actions in Confluence",
        ],
        "note": "Ready for weekly meeting notes. Metrics and impact are deterministic; LLM wording must not invent facts.",
    }


def render_weekly_summary(pack: dict) -> str:
    """Deterministic weekly meeting notes fallback and Confluence draft."""
    fm_sum = pack.get("funnel_metrics") or {}
    latest = fm_sum.get("latest") or {}
    ranks = ((pack.get("impact_ranking") or {}).get("ranking") or [])
    digest = pack.get("execution_digest") or {}
    totals = digest.get("totals") or {}
    lines = [
        f"# Funnel Watchtower Weekly Readout - {pack.get('as_of')}",
        "",
        "## Executive summary",
        f"- Latest month: {fm_sum.get('latest_month')}.",
        f"- E2E conversion: {latest.get('e2e_rate_pct')}%; completion amount: {latest.get('completion_amount_vnd', 0):,} VND.",
        f"- Jira execution: {totals.get('open', 0)} open, {totals.get('off_track', 0)} off-track, {totals.get('due_soon', 0)} due soon.",
    ]
    if ranks:
        top = ranks[0]
        lines.append(f"- Top recovery priority: {top['stage'].title()} ({top['actual_pct']}% vs {top.get('target_pct')}% target), estimated value at risk {im.fmt_vnd(top.get('estimated_value_at_risk_vnd'))}.")
    lines += ["", "## Impact ranking", im.render_ranking(pack.get("impact_ranking") or {}), ""]
    lines += ["## Needs attention now"]
    attention = digest.get("needs_attention_now") or []
    if attention:
        for i in attention[:8]:
            why = []
            if _is_blocked(i):
                why.append("blocked")
            if _is_overdue(i):
                why.append("overdue")
            blocker = _blocker_note(i)
            suffix = f"; {blocker}" if blocker else ""
            lines.append(f"- {i.get('key')}: {i.get('summary')} — owner {i.get('owner')}, workflow status {i.get('status')}, due {i.get('due')} ({', '.join(why)}){suffix}")
    else:
        lines.append("- No blocked or overdue open initiatives.")
    lines += ["", "## Recently completed"]
    done = pack.get("recently_completed") or []
    if done:
        for i in done[:6]:
            lines.append(f"- {i.get('key')}: {i.get('summary')} — owner {i.get('owner')}")
    else:
        lines.append("- No recently completed initiatives returned by Jira.")
    lines += ["", "## Confluence context"]
    pages = _filter_context_pages((pack.get("confluence_decisions") or []) + (pack.get("recent_confluence_pages") or []))
    if pages and pages[0].get("error"):
        lines.append(f"- Could not read Confluence pages: {pages[0].get('error')}")
    elif pages:
        seen = set()
        shown = 0
        for p in pages:
            title = p.get("title") or "Untitled"
            if title in seen:
                continue
            seen.add(title)
            detail = _clean_snippet(p.get("body") or p.get("excerpt") or p.get("url") or "")
            lines.append(f"- {title}: {detail}")
            shown += 1
            if shown >= 6:
                break
    else:
        lines.append("- No recent Confluence pages returned.")
    lines += ["", "## Recommended agenda"]
    for a in pack.get("recommended_agenda") or []:
        lines.append(f"- {a}")
    return "\n".join(lines)
