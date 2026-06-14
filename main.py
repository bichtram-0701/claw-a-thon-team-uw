"""Funnel Watchtower — Team UW, Claw-a-thon 2026.

Execution intelligence for a business funnel. The LLM routes and narrates; Python
and SQL own the business facts: conversion math, value-at-risk ranking, issue
keys, owners, write guards, Jira idempotency, and Confluence weekly summaries.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from greennode_agentbase import GreenNodeAgentBaseApp, PingStatus, RequestContext
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

load_dotenv()

import briefing as bf            # noqa: E402
import confluence_client as cf   # noqa: E402
import contracts as ct           # noqa: E402
import funnel_metrics as fm      # noqa: E402
import impact as im              # noqa: E402
import jira_client as jc         # noqa: E402
import report as rp              # noqa: E402
import router as rt              # noqa: E402
import sql_analyst as sa         # noqa: E402
import teams_client as tc        # noqa: E402

_middleware = [Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])]
try:
    from greennode_agentbase.runtime.app import XAccelBufferingMiddleware
    _middleware.insert(0, Middleware(XAccelBufferingMiddleware))
except ImportError:
    pass

app = GreenNodeAgentBaseApp(middleware=_middleware)
_CHAT_PAGE = os.path.join(os.path.dirname(__file__), "chat.html")


async def _serve_chat(request):
    return FileResponse(_CHAT_PAGE, media_type="text/html")


app.router.routes.append(Route("/", _serve_chat, methods=["GET"]))

JIRA_EVENT_TOKEN = os.environ.get("JIRA_EVENT_TOKEN", "")
ALLOW_WRITES = os.environ.get("ALLOW_WRITES", "true").lower() in ("1", "true", "yes")

STAGE_TO_EPIC = {
    "traffic": "Traffic",
    "submission": "Submission",
    "approval": "Approval",
    "completion": "Completion",
    "crosscut": "Data & Platform",
}


async def _jira_event(request):
    if JIRA_EVENT_TOKEN and request.query_params.get("token") != JIRA_EVENT_TOKEN:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    key = payload.get("key") or (payload.get("issue") or {}).get("key")
    if not key:
        return JSONResponse({"ok": False, "error": "no issue key in payload"}, status_code=400)
    try:
        full = jc.get_issue_full(key)
        changes = jc.get_latest_changes(key)
        sent = tc.change_card(full, changes, header="Task updated")
        return JSONResponse({"ok": True, "key": key, "changes": changes, "sent": sent})
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"ok": False, "key": key, "error": str(e)}, status_code=200)


app.router.routes.append(Route("/jira-event", _jira_event, methods=["POST"]))


# ---------------------------------------------------------------- routing ----
def route(message: str) -> str:
    """LLM-first semantic routing with keyword fallback."""
    return rt.route(message)


def _keyword_route(message: str) -> str:
    return rt.keyword_route(message)


# --------------------------------------------------------------- write utils --
_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
_CREATE_PREFIX = re.compile(
    r"^\s*(please\s+)?(create|add|open|file|log|make|new)\b[^:]*?(ticket|initiative|task|issue)?\s*[:\-]?\s*",
    re.IGNORECASE,
)


def extract_create_fields(message: str) -> dict:
    """Extract a Jira initiative; validate LLM JSON before use."""
    raw = rp.llm_chat(
        "Extract a Jira initiative from the user's message as STRICT JSON only. Keys: "
        "summary (short imperative string), stage (traffic/submission/approval/completion/crosscut/null), "
        "owner (person name or null), due (YYYY-MM-DD or null), confidence (low/medium/high or null), "
        "target_lift_pp (number or null), evidence (array of short strings or null). "
        "Infer stage only when obvious: acquisition/eligible traffic->traffic; submit/docs/KYC/form->submission; "
        "approval/review/risk/income->approval; payout/e-sign/final outcome->completion; shared data/platform->crosscut.",
        message,
        max_tokens=360,
        temperature=0.0,
        profile="classifier",
    )
    fields = rp.extract_json_object(raw)
    if not fields or not fields.get("summary"):
        summary = _CREATE_PREFIX.sub("", message).strip().rstrip("?.!") or message.strip()
        fields = {"summary": summary, "stage": ct.infer_stage(message), "owner": None,
                  "due": None, "confidence": "low", "evidence": [message]}
    return ct.validate_create_fields(fields, message)


def parse_assign(message: str):
    """Pull an issue key and target owner from e.g. 'assign UW-23 to Mai'."""
    m = _KEY_RE.search(message)
    key = m.group(1) if m else None
    owner = None
    mt = re.search(r"\bto\s+([A-Za-z][\w '.-]*)$", message.strip())
    if mt:
        owner = mt.group(1).strip().rstrip(" ?.! ")
    return key, owner


NARRATE_SYS = {
    "oversight": "Lead with impact_ranking.ranking[0] if present, then needs_attention_now, due_soon, by_epic, and overloaded owners. Quote issue keys and owners. For blocked items, clarify that blocked is a label/flag, not necessarily the Jira workflow status; include blocked_by and blocks when present.",
    "briefing": "Summarize the user's plate: blocked/overdue first, then active work. Quote issue keys. For blocked items, say what they are blocked by if the JSON includes blocked_by.",
    "sprint": "Give a team health summary: open vs done, status mix, blockers, overdue, and workload by owner. For blocked items, clarify what dependency blocks them and what work they block when the JSON includes blocked_by/blocks.",
    "knowledge": "Answer using ONLY the provided Confluence pages. Quote page title and URL. If the pages do not answer it, say so plainly.",
    "standup": "Write a ready-to-paste standup with Yesterday / Today / Blockers using issue keys.",
}


def _needs_atlassian(intent: str) -> bool:
    return intent in {"create", "assign", "flag", "oversight", "briefing", "sprint", "knowledge", "standup", "weekly"}


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    try:
        return _handle(payload)
    except Exception as e:  # noqa: BLE001 — never expose a bare 500 to chat UI
        import traceback
        return {
            "status": "error",
            "answer": "Sorry, something went wrong with that question. Try rephrasing.",
            "error": type(e).__name__ + ": " + str(e),
            "trace_tail": traceback.format_exc().splitlines()[-3:],
            "timestamp": datetime.now().isoformat(),
        }


def _handle(payload: dict) -> dict:
    message = str(payload.get("message", ""))
    lang = payload.get("language", "en")
    rr = rt.route_result(message)
    intent = rr.intent
    route_info = rr.__dict__

    if _needs_atlassian(intent) and not jc.configured():
        return _respond(intent,
                        "I cannot reach Jira/Confluence right now because Atlassian credentials are not configured.",
                        {"error": "Atlassian credentials not configured", "route": route_info})

    if intent in ("create", "assign"):
        return _handle_write(intent, message, route_info)
    if intent == "flag":
        return _handle_flag(message, route_info)
    if intent == "weekly":
        return _handle_weekly(message, lang, route_info)

    answer = None
    if intent == "analyst":
        if not sa.configured():
            result = {"error": "analyst data not available", "route": route_info}
            answer = "The application-level dataset is not available on this deployment."
        else:
            result = sa.answer(message)
            result["route"] = route_info
            if result.get("error"):
                answer = (f"I could not run that analysis ({result['error']}). Try e.g. "
                          "daily volume in May, May applications by product, or by drop reason.")
            else:
                answer = sa.to_markdown(result)
                if result.get("source") == "template":
                    answer = f"_Template: {result.get('template')}_\n\n" + answer
                if result.get("sql"):
                    answer += "\n\n_SQL:_ `" + result["sql"] + "`"
    elif intent == "metrics":
        result = _metrics_result(route_info)
        answer = _render_metrics_answer(result, lang)
    elif intent == "oversight":
        result = bf.manager_digest()
        result["route"] = route_info
    elif intent == "briefing":
        result = bf.my_briefing()
        result["route"] = route_info
    elif intent == "sprint":
        result = bf.sprint_pulse()
        result["route"] = route_info
    elif intent == "knowledge":
        result = bf.knowledge(message)
        result["route"] = route_info
    elif intent == "standup":
        result = bf.standup_draft()
        result["route"] = route_info
    else:
        result = {"route": route_info,
                  "hint": "Try: funnel metrics, value at risk, daily volume in May, funnel overview, flag it, weekly meeting summary, create a ticket, assign UW-12 to Mai, or draft my standup."}
        answer = (
            "Hi, I am Funnel Watchtower. I track the business funnel, rank target misses by value at risk, "
            "connect them to Jira ownership, answer safe SQL-style breakdowns, summarize Confluence decisions, "
            "draft weekly meeting briefs, and create or update Jira recovery work.\n\n"
            "Best prompt pattern: **action + stage/metric + time period**. Examples: `show daily volume in May`, "
            "`break May drop reasons by transition`, `why did approval drop?`, `flag the approval drop`, "
            "or `publish weekly meeting summary to Confluence`.\n\n"
            "Funnel stages: **Traffic → Submission → Approval → Completion**. If you ask only for `volume`, I default "
            "to all funnel-stage counts. If you ask only for `drop reason`, I highlight the highest-risk transition."
        )

    if answer is None:
        sys_extra = NARRATE_SYS.get(intent, "")
        lang_line = "Answer in Vietnamese." if lang == "vi" else "Answer in the user's language, default English."
        out = rp.llm_chat(
            "You are Funnel Watchtower, a business-funnel execution intelligence assistant. "
            "Use ONLY the JSON data provided. Never invent issue keys, owners, page titles, URLs, numbers, or decisions. "
            "Answer the user's actual question first. For a narrow factual question, use 1-2 sentences. "
            "If the user asks about 'blocked', explain that it can be a Jira label/flag while the workflow status may still be To Do/In Progress. "
            "For a digest, use clear markdown. " + sys_extra + " " + lang_line,
            "Question: " + message + "\nData JSON:\n" + json.dumps(result, ensure_ascii=False),
            max_tokens=1000,
            temperature=0.2,
        )
        answer = out or json.dumps(result, ensure_ascii=False, indent=2)

    return _respond(intent, answer, result)


def _metrics_result(route_info: dict | None = None) -> dict:
    result = fm.summary()
    open_issues = []
    owners = {}
    if jc.configured():
        try:
            open_issues = jc.all_open_issues()
            owners = bf.stage_owners_from_issues(open_issues)
        except Exception:  # noqa: BLE001
            open_issues = []
            owners = {}
    result["impact_ranking"] = im.rank_stage_risks(open_issues, owners)
    if route_info is not None:
        result["route"] = route_info
    return result


def _render_metrics_answer(result: dict, lang: str) -> str:
    lang_hint = "Reply in Vietnamese." if lang == "vi" else "Reply in English."
    headline = rp.llm_chat(
        "You are Funnel Watchtower. In 1-2 sentences give the lead the headline trend from this funnel data. "
        "Name the latest month, end-to-end rate, top target miss/value-at-risk if present, and the most notable MoM change. "
        "Use ONLY the JSON numbers. " + lang_hint,
        json.dumps({k: result.get(k) for k in ["latest_month", "latest", "mom_pp", "target_misses", "impact_ranking"]}, ensure_ascii=False),
        max_tokens=220,
        temperature=0.2,
    )
    heads_up = ""
    ranking = (result.get("impact_ranking") or {}).get("ranking") or []
    if ranking:
        top = ranking[0]
        heads_up = (
            f"> ⚠ **Top recovery priority:** {top['stage'].title()} — "
            f"estimated value at risk {im.fmt_vnd(top.get('estimated_value_at_risk_vnd'))}; "
            f"score {top.get('score')}. Say `flag it` to open or update the investigation.\n\n"
            f"**Impact ranking**\n\n{im.render_ranking(result.get('impact_ranking'))}\n\n"
        )
    return heads_up + (headline + "\n\n" if headline else "") + fm.render_markdown()


def _handle_weekly(message: str, lang: str, route_info: dict) -> dict:
    pack = bf.weekly_meeting_pack()
    pack["route"] = route_info
    publish = any(k in message.lower() for k in ["publish", "post", "save", "create page", "write to confluence", "post to confluence"])

    # Use the deterministic weekly summary as the canonical meeting artifact.
    # This keeps Confluence pages stable and prevents the LLM from changing
    # formatting, issue counts, or value-at-risk wording between runs.
    answer = bf.render_weekly_summary(pack)
    result = dict(pack)
    if publish:
        if not ALLOW_WRITES:
            answer += "\n\n(Writes are off, so I drafted the weekly summary but did not publish it to Confluence.)"
            result["published"] = False
            result["publish_error"] = "ALLOW_WRITES=false"
        else:
            page = cf.upsert_page(cf.weekly_title(pack.get("as_of")), answer)
            result["confluence_page"] = page
            result["published"] = bool(page.get("id"))
            if page.get("url"):
                answer += f"\n\nPublished to Confluence: {page['url']}"
            else:
                answer += f"\n\nCould not publish to Confluence ({page.get('error', 'unknown error')})."
    return _respond("weekly", answer, result)


def _handle_flag(message: str, route_info: dict) -> dict:
    drops = fm.anomalies()
    misses = fm.target_misses()
    if not drops and not misses:
        return _respond("flag", "No significant drops or target misses right now — the funnel looks stable.",
                        {"anomalies": [], "target_misses": [], "route": route_info})

    try:
        open_issues = jc.all_open_issues()
    except Exception:  # noqa: BLE001
        open_issues = []
    owners = bf.stage_owners_from_issues(open_issues)
    ranking_pack = im.rank_stage_risks(open_issues, owners)
    ranked_by_stage = {x["stage"]: x for x in ranking_pack.get("ranking", [])}

    reasons: dict[str, list[str]] = {}
    for a in drops:
        reasons.setdefault(a["stage"], []).append(
            f"{a['metric']} dropped {abs(a['delta_pp'])}pp MoM ({a['prev_pct']}%→{a['latest_pct']}%)")
    for mm in misses:
        reasons.setdefault(mm["stage"], []).append(
            f"{mm['metric']} {mm['actual_pct']}% vs {mm['target_pct']}% target ({mm['gap_pp']}pp)")

    lines, actions = [], []
    for stage in sorted(reasons, key=lambda s: ranked_by_stage.get(s, {}).get("rank", 99)):
        why = reasons[stage]
        risk = ranked_by_stage.get(stage, {})
        owner = owners.get(stage) or risk.get("owner")
        diagnostic = sa.diagnostic_findings(stage + " drop") if sa.configured() else {}
        contract = im.investigation_contract(stage, why, owner, risk, diagnostic)
        description = ct.contract_markdown(contract, title="Investigation contract")
        metric = contract.get("metric")
        month = risk.get("month") or fm.summary().get("latest_month")
        metric_label = str(metric or stage).replace("_rate_pct", "-rate").replace("_", "-")
        labels_extra = ["investigation", "month-" + str(month), "metric-" + metric_label]

        line = f"**{stage.title()}**: " + "; ".join(why)
        if risk.get("estimated_value_at_risk_vnd"):
            line += f"; estimated value at risk {im.fmt_vnd(risk.get('estimated_value_at_risk_vnd'))}"
        if owner:
            line += f"; owner: {owner}"

        if ALLOW_WRITES:
            assignee_id = None
            if owner:
                try:
                    user = jc.find_assignable_user(owner)
                    if user:
                        assignee_id = user["accountId"]
                except Exception:  # noqa: BLE001
                    assignee_id = None
            existing = None
            try:
                existing = jc.find_open_investigation(stage, metric=metric, month=str(month))
            except Exception:  # noqa: BLE001
                existing = None
            if existing:
                try:
                    jc.comment_issue(existing["key"], "Funnel Watchtower refreshed this investigation.\n\n" + description)
                except Exception:  # noqa: BLE001
                    pass
                line += f" → updated existing {existing['key']}"
                actions.append({"stage": stage, "action": "updated", "key": existing["key"], "contract": contract})
            else:
                epic_name = STAGE_TO_EPIC.get(stage)
                try:
                    epic_key = jc.find_epic(epic_name) if epic_name else None
                except Exception:  # noqa: BLE001
                    epic_key = None
                title = f"Investigate {stage.title()}: " + "; ".join(why)
                res = jc.create_issue(summary=title, stage=stage, owner=None, due=None,
                                      assignee_id=assignee_id, epic_key=epic_key,
                                      labels_extra=labels_extra, description=description)
                if res.get("key"):
                    line += f" → opened {res['key']}" + (f" for {owner}" if owner else "")
                    actions.append({"stage": stage, "action": "created", "key": res["key"], "contract": contract})
                else:
                    line += " (could not open task)"
                    actions.append({"stage": stage, "action": "error", "error": res.get("error"), "contract": contract})
        lines.append("- " + line)

    created = [a["key"] for a in actions if a.get("action") == "created"]
    updated = [a["key"] for a in actions if a.get("action") == "updated"]
    verb = "Flagged"
    if created or updated:
        parts = []
        if created:
            parts.append(f"created {len(created)}")
        if updated:
            parts.append(f"updated {len(updated)}")
        verb += " and " + " / ".join(parts) + " investigation(s)"
    answer = f"{verb} for {len(reasons)} stage(s):\n\n" + "\n".join(lines)
    if not ALLOW_WRITES:
        answer += "\n\n(Writes are off, so I only flagged them.)"
    return _respond("flag", answer, {
        "anomalies": drops,
        "target_misses": misses,
        "impact_ranking": ranking_pack,
        "stages": list(reasons),
        "actions": actions,
        "created": created,
        "updated": updated,
        "route": route_info,
    })


def _handle_write(intent: str, message: str, route_info: dict) -> dict:
    if not ALLOW_WRITES:
        return _respond(intent, "Writing to Jira is disabled on this deployment (set ALLOW_WRITES=true to enable).",
                        {"allow_writes": False, "route": route_info})

    if intent == "create":
        f = extract_create_fields(message)
        owner = f.get("owner")
        assignee_id = None
        assign_note = ""
        if owner:
            user = jc.find_assignable_user(owner)
            if user:
                assignee_id = user["accountId"]
                assign_note = f"assigned to {user['displayName']}"
            else:
                assign_note = f"tagged {jc.owner_label(owner)}"
        else:
            me = jc.myself()
            if me:
                assignee_id = me["accountId"]
                assign_note = f"assigned to you ({me['displayName']})"

        stage = f.get("stage")
        epic_name = STAGE_TO_EPIC.get(stage) if stage else None
        epic_key = jc.find_epic(epic_name) if epic_name else None
        description = ct.contract_markdown(f, title="Initiative contract")
        res = jc.create_issue(summary=f["summary"], stage=stage, owner=owner, due=f.get("due"),
                              assignee_id=assignee_id, epic_key=epic_key, description=description)
        if res.get("error"):
            return _respond("create", f"Could not create that initiative ({res['error']}).", {**res, "route": route_info})
        bits = []
        if epic_name:
            bits.append(f"Epic: {epic_name}" + ("" if res.get("epic_key") else " (label only)"))
        bits.append(f"due {f['due']}" if f.get("due") else "backlog (no due date)")
        if assign_note:
            bits.append(assign_note)
        answer = f"Created **{res['key']}** — {f['summary']}"
        if bits:
            answer += " (" + ", ".join(bits) + ")"
        answer += f". {res['url']}"
        return _respond("create", answer, {**res, "fields": f, "contract": f, "route": route_info})

    key, owner = parse_assign(message)
    if not key or not owner:
        return _respond("assign", "Tell me which ticket and who, e.g. `assign UW-23 to Mai`.",
                        {"parsed": {"key": key, "owner": owner}, "route": route_info})
    user = jc.find_assignable_user(owner)
    res = jc.assign_issue(key, assignee_id=(user["accountId"] if user else None), owner=owner)
    if user and res.get("assigned_real"):
        answer = f"Assigned **{key}** to {user['displayName']} (owner label stamped too)."
    elif res.get("owner_label"):
        answer = f"Set **{key}** owner to {owner} via label {res['owner_label']}."
    else:
        answer = f"Could not assign {key} ({res.get('error', 'unknown error')})."
    res["route"] = route_info
    return _respond("assign", answer, res)


def _respond(intent: str, answer, result: dict) -> dict:
    return {
        "status": "success",
        "intent": intent,
        "answer": answer,
        "result": result,
        "version": os.environ.get("GIT_SHA", "dev")[:7],
        "disclaimer": "Synthetic workspace data — Claw-a-thon 2026 demo.",
        "timestamp": datetime.now().isoformat(),
    }


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
