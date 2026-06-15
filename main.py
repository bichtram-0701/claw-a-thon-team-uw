"""Funnel Agent — Team UW, Claw-a-thon 2026.

Execution intelligence for a business funnel. The LLM routes and narrates; Python
and SQL own the business facts: conversion math, value-at-risk ranking, issue
keys, owners, write guards, Jira idempotency, and Confluence weekly summaries.
"""
from __future__ import annotations

import calendar
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

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


async def _version(request):
    return JSONResponse({
        "app_version": APP_VERSION,
        "build_version": BUILD_VERSION,
        "jira_project_key": os.environ.get("JIRA_PROJECT_KEY", ""),
        "allow_writes": ALLOW_WRITES,
    })


app.router.routes.append(Route("/version", _version, methods=["GET"]))

JIRA_EVENT_TOKEN = os.environ.get("JIRA_EVENT_TOKEN", "")
ALLOW_WRITES = os.environ.get("ALLOW_WRITES", "true").lower() in ("1", "true", "yes")
APP_VERSION = os.environ.get("APP_VERSION", "demo-v14")
BUILD_VERSION = os.environ.get("GIT_SHA", "dev")[:7]

STAGE_TO_EPIC = {
    "traffic": "Traffic",
    "submission": "Submission",
    "approval": "Approval",
    "completion": "Disbursement",
    "crosscut": "Data & Platform",
}


def _default_owner_for_stage(stage: str | None) -> str | None:
    """Return the operational stage owner used as the default Jira assignee.

    Demo convention: each funnel Epic represents a stage. Open tasks under that
    stage reveal the operational owner. If a Jira write does not name an owner,
    Watchtower defaults to this stage owner rather than leaving the task
    unassigned or assigning everything to the token owner. Environment variables
    can override the demo inference, e.g. DEFAULT_STAGE_OWNER_APPROVAL=bichtram.
    """
    st = (stage or "").strip().lower()
    if not st:
        return None
    env_name = "DEFAULT_STAGE_OWNER_" + st.upper().replace("-", "_")
    owner = os.environ.get(env_name) or os.environ.get("DEFAULT_OWNER_" + st.upper().replace("-", "_"))
    if owner:
        return owner.strip()
    try:
        inferred = bf.stage_owners().get(st)
        if inferred and inferred != "Unassigned":
            return inferred
    except Exception:  # noqa: BLE001
        return None
    return None


def _default_owner_note(stage: str | None, owner: str | None, real_assignee: str | None = None) -> str:
    if not stage or not owner:
        return ""
    label = STAGE_TO_EPIC.get(stage, stage.title())
    who = real_assignee or owner
    return f"No assignee was mentioned; defaulting to **{who}**, the **{label}** stage owner from the Epic → task structure."


# Real-time dedup state (single replica): issue key -> (updated_stamp, monotonic)
_RECENT_EVENTS: dict = {}
_DEDUP_WINDOW_SEC = 90      # collapse duplicate rule firings for the same change
_CREATE_GRACE_SEC = 60      # created ~= updated within this -> treat as a new task


def _parse_iso(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except Exception:  # noqa: BLE001
        return None


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
        event = str(payload.get("event") or "").lower()
        # Dedupe near-simultaneous events: a single create/edit can trigger both
        # the "created" and "field value changed" automation rules (and Jira may
        # fire several field changes at once). Same issue + same `updated` stamp
        # within the window -> notify once. (Single replica -> in-memory is fine.)
        sig = str(full.get("updated_ts") or full.get("updated"))
        now = time.monotonic()
        prev = _RECENT_EVENTS.get(key)
        _RECENT_EVENTS[key] = (sig, now)
        if len(_RECENT_EVENTS) > 2000:
            for k in [k for k, (_, t) in _RECENT_EVENTS.items() if now - t > _DEDUP_WINDOW_SEC]:
                _RECENT_EVENTS.pop(k, None)
        if prev and prev[0] == sig and (now - prev[1]) < _DEDUP_WINDOW_SEC:
            return JSONResponse({"ok": True, "key": key, "deduped": True, "sent": False})

        # A freshly created task (created ~= updated) is always a "new task",
        # regardless of which rule fired first -> correct header + no dup.
        cu = _parse_iso(full.get("created_ts") or full.get("created"))
        uu = _parse_iso(full.get("updated_ts") or full.get("updated"))
        just_created = bool(cu and uu and (uu - cu).total_seconds() < _CREATE_GRACE_SEC)
        changes = jc.get_latest_changes(key)
        if event == "created" or just_created:
            sent = tc.issue_card(full, header="New task created")
            kind = "created"
        else:
            sent = tc.change_card(full, changes, header="Task updated")
            kind = "updated"
        return JSONResponse({"ok": True, "key": key, "kind": kind, "changes": changes, "sent": sent})
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
# Explicit assignee in a create message, e.g. "assignee = bichtram", "assigned to Mai".
_OWNER_RE = re.compile(
    r"\b(?:assignee|assigned to|assign to|giao cho|gan cho|gán cho)\b\s*[:=]?\s*([A-Za-z][\w.'-]*)",
    re.IGNORECASE,
)


def _today_vn() -> str:
    """Today's date in Asia/Bangkok (UTC+7) — the team/Jira timezone."""
    return (datetime.now(timezone.utc) + timedelta(hours=7)).date().isoformat()


def extract_create_fields(message: str) -> dict:
    """Extract a Jira initiative; validate LLM JSON before use."""
    today = _today_vn()
    raw = rp.llm_chat(
        "Extract a Jira initiative from the user's message as STRICT JSON only. Keys: "
        "summary (short imperative string), stage (traffic/submission/approval/completion/crosscut/null), "
        "owner (the person to assign the task to — look for 'assignee', 'assigned to', "
        "'assign to', 'owner', 'giao cho'; the person's name, else null), "
        "due (YYYY-MM-DD or null), confidence (low/medium/high or null), "
        "target_lift_pp (number or null), evidence (array of short strings or null). "
        f"Today's date is {today} (Asia/Bangkok). Resolve relative due dates against it: "
        "'today'->today's date, 'tomorrow'->+1 day, 'next week'->+7 days, 'end of week'->coming Friday, "
        "'in N days'->+N days. NEVER output a past date for a future-sounding request; output absolute YYYY-MM-DD. "
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
        # If the user writes the create action at the end (`investigate traffic drop..., create a ticket`),
        # keep the Jira summary focused on the requested investigation rather than the whole sentence.
        low = message.lower()
        if "create" in low and "ticket" in low and "investigate" in low:
            stage = ct.infer_stage(message)
            month_match = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b", low)
            month_txt = (" in " + month_match.group(1).title()) if month_match else ""
            if stage:
                summary = f"Investigate {stage.title()} drop{month_txt}"
        fields = {"summary": summary, "stage": ct.infer_stage(message), "owner": None,
                  "due": None, "confidence": "low", "evidence": [message]}
    # Regex fallback: catch "assignee = X" / "assigned to X" / "giao cho X" when
    # the LLM missed the owner, so explicit assignees are never dropped.
    if not fields.get("owner"):
        m = _OWNER_RE.search(message)
        if m:
            fields["owner"] = m.group(1).strip()
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
    return intent in {"create", "assign", "flag", "oversight", "briefing", "sprint", "knowledge", "standup", "weekly", "teams"}


def _prefix_required_answer(rr, original_message: str) -> str:
    interpreted = rr.interpreted_as or original_message.strip()
    prefix = rr.prefix or (interpreted.split(":", 1)[0] if ":" in interpreted else "jira")
    if rr.source == "strict_guard":
        return (
            "⚠️ **Command prefix required.** Start your message with one of: "
            "`/metrics`, `/query`, `/jira`, `/confluence`, `/teams`, `/help`.\n\n"
            f"Suggested rewrite: `{interpreted}`"
        )
    if rr.intent in {"create", "assign", "flag"}:
        system = "Jira"
        prefix = "jira"
    elif rr.intent == "teams":
        system = "Teams"
        prefix = "teams"
    elif rr.intent == "weekly":
        system = "Confluence"
        prefix = "confluence"
    else:
        system = "external"
    return (
        f"⚠️ This looks like a **{system} write/action**. For safety, I did not execute it without an explicit slash command.\n\n"
        f"Please resend as: `{interpreted}`\n\n"
        "Read-only questions can still be answered without a slash command, but I will show an interpretation warning. "
        "For exact routing, use `/metrics`, `/query`, `/jira`, `/confluence`, `/teams`, or `/help`."
    )


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
    original_message = str(payload.get("message", ""))
    lang = payload.get("language", "en")
    rr = rt.route_result(original_message)
    intent = rr.intent
    message = rr.stripped_message or original_message
    route_info = rr.__dict__

    if rr.needs_clarification:
        return _respond("help", rr.clarification or "Please clarify the funnel stage, month, or target system.",
                        {"route": route_info, "clarification_required": True})
    if rr.needs_prefix:
        return _respond(intent, _prefix_required_answer(rr, original_message),
                        {"route": route_info, "prefix_required": True})

    if _needs_atlassian(intent) and not jc.configured():
        return _respond(intent,
                        "I cannot reach Jira/Confluence right now because Atlassian credentials are not configured.",
                        {"error": "Atlassian credentials not configured", "route": route_info})

    if intent in ("create", "assign"):
        return _handle_write(intent, message, route_info)
    if intent == "flag":
        return _handle_flag(message, route_info)
    if intent == "teams":
        return _handle_teams(message, route_info)
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
                intro = _analyst_intro(result)
                if intro:
                    answer = intro + "\n\n" + answer
                if result.get("source") == "template":
                    answer = f"_Template: {result.get('template')}_\n\n" + answer
                if result.get("sql"):
                    answer += "\n\n_SQL:_ `" + result["sql"] + "`"
    elif intent == "metrics":
        cmp_months = _comparison_months_from_message(message)
        if _is_target_disbursement_question(message):
            result = _metrics_result(route_info)
            answer = _render_target_disbursement_answer(result)
        elif _is_investigation_result_question(message):
            result = _metrics_result(route_info)
            answer = _render_investigation_result_answer(message, result)
        elif cmp_months:
            result = _month_comparison_result(cmp_months, route_info)
            answer = _render_month_comparison_answer(result)
        else:
            scoped_month = _scoped_metric_month_from_message(message)
            if scoped_month:
                result = _metrics_result(route_info, month=scoped_month)
                if _is_top_risk_question(message) or _is_recovery_priority_question(message):
                    answer = _render_top_risk_answer(result, month=scoped_month)
                else:
                    answer = _render_metrics_answer(result, lang, month=scoped_month)
            else:
                result = _metrics_result(route_info)
                if _is_top_risk_question(message):
                    answer = _render_top_risk_answer(result)
                else:
                    answer = _render_metrics_answer(result, lang)
    elif intent == "oversight":
        result = bf.manager_digest()
        result["route"] = route_info
        if _is_epic_assignment_question(message):
            answer = _render_epic_assignment_answer(result)
        elif _is_unassigned_work_question(message):
            answer = _render_unassigned_work_answer(result)
        elif _is_epic_owner_question(message):
            answer = _render_epic_owner_answer(result)
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
                  "hint": "Try: /metrics show me the funnel metrics, /query show daily volume in May, /jira what is critical or off track, /jira flag it, /confluence weekly meeting summary, /jira create a ticket, or /help how should I ask questions."}
        if _is_database_help_question(message) and not _is_command_help_question(message):
            answer = sa.schema_guide_markdown()
        else:
            answer = (
                "Hi, I am Funnel Agent. I track the business funnel, rank target misses by value at risk, "
                "connect them to Jira ownership, answer safe query-style breakdowns, summarize Confluence decisions, "
                "draft weekly meeting briefs, post Jira digests to Teams, and create or update Jira recovery work.\n\n"
                "Best prompt pattern: **slash command + action + stage/metric + time period**. Slash commands give exact routing: "
                "`/metrics`, `/query`, `/jira`, `/confluence`, `/teams`, and `/help`.\n\n"
                "Use `/metrics` for business KPI readouts: funnel health, MoM comparison, top risk, and value at risk. "
                "Use `/query` for row-level data drilldowns: daily volume, drop reasons, channel/product breakdowns, and safe SQL templates.\n\n"
                "Examples: `/metrics show me the funnel metrics`, `/metrics why is approval the top risk?`, "
                "`/query break May approval drop down by reason`, `/jira flag the drops and assign owners to investigate`, "
                "`/teams post off-track blockers`, `/confluence weekly meeting summary`, or "
                "`/confluence publish weekly meeting summary to Confluence`.\n\n"
                "Funnel stages: **Traffic → Submission → Approval → Disbursement**. Jira work follows an "
                "**Epic → stage owner → task assignee** structure: when a Jira write does not name an assignee, "
                "Watchtower defaults to that stage's operational owner. Read-only questions without a slash command "
                "still work with an interpretation warning; writes require the explicit command. "
                "For month-over-month, ask `/metrics compare April and May performance`."
            )

    if answer is None:
        sys_extra = NARRATE_SYS.get(intent, "")
        lang_line = "Answer in Vietnamese." if lang == "vi" else "Answer in the user's language, default English."
        out = rp.llm_chat(
            "You are Funnel Agent, a business-funnel execution intelligence assistant. "
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


def _analyst_intro(result: dict) -> str:
    template = result.get("template") or ""
    rows = result.get("rows") or []
    if template.endswith("_diagnostic_contribution"):
        stage = template.replace("_diagnostic_contribution", "").title()
        return (f"**{stage} diagnostic view.** This is contribution analysis, not causal proof. "
                "It compares pass/drop rates by channel and product type for the selected month.")
    if template == "approval_drop_reason_breakdown" and rows:
        try:
            start = rows[0][3]
            passed = rows[0][4]
            dropped = rows[0][5]
            return (f"**Submission → Approval reconciliation:** {start} submitted, {passed} approved, "
                    f"so {dropped} dropped before Approval. The table below explains those dropped rows only.")
        except Exception:  # noqa: BLE001
            return "**Submission → Approval drop breakdown.** The table below explains submitted rows that did not reach Approval."
    if template == "submission_drop_reason_breakdown" and rows:
        return "**Traffic → Submission drop breakdown.** The table below explains traffic rows that did not submit."
    if template == "completion_drop_reason_breakdown" and rows:
        return "**Approval → Disbursement drop breakdown.** The table below explains approved rows that did not disburse."
    if template == "daily_volume" and rows:
        try:
            cols = result.get("columns") or []
            idx = {c: i for i, c in enumerate(cols)}
            apps = sum(int(r[idx["applications"]] or 0) for r in rows)
            submitted = sum(int(r[idx["submitted"]] or 0) for r in rows)
            approved = sum(int(r[idx["approved"]] or 0) for r in rows)
            disbursed_col = idx.get("disbursed", idx.get("completed"))
            disbursed = sum(int(r[disbursed_col] or 0) for r in rows) if disbursed_col is not None else 0
            return (f"**Daily funnel volume.** Totals reconcile to the monthly funnel: "
                    f"{apps} Traffic, {submitted} Submission, {approved} Approval, {disbursed} Disbursement.")
        except Exception:  # noqa: BLE001
            return "**Daily funnel volume.** Counts are grouped by entry date and include all funnel stages."
    return ""


def _metrics_result(route_info: dict | None = None, month: str | None = None) -> dict:
    result = fm.summary_for_month(month) if month else fm.summary()
    open_issues = []
    owners = {}
    if jc.configured():
        try:
            open_issues = jc.all_open_issues()
            owners = bf.stage_owners_from_issues(open_issues)
        except Exception as e:  # noqa: BLE001
            open_issues = []
            owners = {}
            result["jira_context_error"] = type(e).__name__ + ": " + str(e)[:180]
    result["impact_ranking"] = (
        im.rank_stage_risks_for_month(month, open_issues, owners) if month
        else im.rank_stage_risks(open_issues, owners)
    )
    if route_info is not None:
        result["route"] = route_info
    return result


def _render_metrics_answer(result: dict, lang: str, month: str | None = None) -> str:
    lang_hint = "Reply in Vietnamese." if lang == "vi" else "Reply in English."
    headline = rp.llm_chat(
        "You are Funnel Agent. In 1-2 sentences give the lead the headline trend from this funnel data. "
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
            f"score {top.get('score')}. Say `/jira flag it` to open or update the investigation.\n\n"
            f"**Impact ranking**\n\n{im.render_ranking(result.get('impact_ranking'))}\n\n"
        )
    jira_warn = ""
    if result.get("jira_context_error"):
        jira_warn = (
            "> Note: I could compute funnel metrics, but Jira context could not be read, "
            "so owners/blockers may be incomplete. "
            f"Debug: `{result.get('jira_context_error')}`\n\n"
        )
    scope_note = f"> Month-scoped view: treating {month} as the latest visible month; later months are excluded.\n\n" if month else ""
    return jira_warn + scope_note + heads_up + (headline + "\n\n" if headline else "") + fm.render_markdown(month)


def _is_top_risk_question(message: str) -> bool:
    q = message.lower()
    return any(k in q for k in ["top risk", "top recovery", "recovery priority", "why is approval", "why approval is"])


def _is_recovery_priority_question(message: str) -> bool:
    q = message.lower()
    return any(k in q for k in ["recovery priority", "priority", "prioritize", "prioritise", "top recovery", "what should we do first"])


def _is_command_help_question(message: str) -> bool:
    q = message.lower()
    return any(k in q for k in [
        "difference between metrics", "metrics and sql", "metrics vs sql",
        "metrics and query", "metrics vs query", "what is /metrics", "what is /query",
        "what is metrics", "what is query", "slash command", "prefix",
    ])


def _is_database_help_question(message: str) -> bool:
    q = message.lower()
    return any(k in q for k in ["query the database", "query database", "database", "schema", "what table", "duckdb", "how do i query"])


def _scoped_metric_month_from_message(message: str) -> str | None:
    """Return a YYYY-MM for month-scoped metric/risk prompts that are not comparisons."""
    q = message.lower()
    if _comparison_months_from_message(message):
        return None
    # Metrics prompts that ask to exclude/cut off the latest month should use the
    # final named month as the requested as-of month.
    year_m = re.search(r"\b(20\d{2})\b", q)
    default_year = int(year_m.group(1)) if year_m else 2026
    found: list[tuple[int, str]] = []
    for m in re.finditer(r"\b(20\d{2})-(\d{1,2})\b", q):
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            found.append((m.start(), f"{y}-{mo:02d}"))
    for name, num in _MONTH_WORDS.items():
        for m in re.finditer(rf"\b{re.escape(name)}\b", q):
            found.append((m.start(), f"{default_year}-{num:02d}"))
    if not found:
        return None
    ordered = [month for _, month in sorted(found, key=lambda x: x[0])]
    # Avoid changing generic latest-month prompts unless the user explicitly
    # asks for metrics/risk as of a named month.
    if any(k in q for k in ["in ", "as of", "cutoff", "cut off", "exclude", "without", "before", "up to", "through"]):
        return ordered[-1]
    return ordered[-1] if len(set(ordered)) == 1 else None



def _is_target_disbursement_question(message: str) -> bool:
    q = message.lower()
    return ("target" in q and any(k in q for k in ["disbursement", "disburse", "completion", "complete"]) 
            and any(k in q for k in ["volume", "count", "amount", "value", "target"]))


def _render_target_disbursement_answer(result: dict) -> str:
    row = result["summary"]["latest"] if "summary" in result else fm.summary()["latest"]
    targets = fm.targets()
    traffic = row.get("traffic") or 0
    approvals = row.get("approval") or 0
    disb = row.get("completion") or 0
    amount = row.get("completion_amount_vnd") or 0
    avg = row.get("avg_ticket_vnd") or 0
    e2e_target = targets.get("e2e_rate_pct")
    disb_rate_target = targets.get("completion_rate_pct")
    e2e_target_count = round(traffic * (e2e_target or 0) / 100) if e2e_target is not None else None
    rate_target_count = round(approvals * (disb_rate_target or 0) / 100) if disb_rate_target is not None else None
    lines = [
        "There is **no standalone Disbursement volume OKR** configured in the demo data. Watchtower has rate targets, so the target volume depends on which target you mean.",
        "",
        f"For **{row.get('month')}**:",
        f"- Actual Disbursement count: **{disb:,}**",
        f"- Actual Disbursement volume: **{amount:,.0f} VND**",
    ]
    if e2e_target_count is not None:
        lines.append(f"- Implied volume to hit the **Traffic E2E target ({e2e_target}%)**: about **{e2e_target_count:,} disbursements** from {traffic:,} traffic")
    if rate_target_count is not None:
        lines.append(f"- Implied volume to hit the **Disbursement rate target ({disb_rate_target}%)**: about **{rate_target_count:,} disbursements** from {approvals:,} approvals")
    lines += [
        "",
        "So if you mean the board-style count row, use **Disbursement (4)**. If you mean money, use **Disbursement Volume**.",
    ]
    return "\n".join(lines)


def _is_investigation_result_question(message: str) -> bool:
    q = message.lower()
    return ("investigat" in q or "result" in q or "outcome" in q) and any(k in q for k in ["submission", "approval", "traffic", "disbursement", "completion"])


def _render_investigation_result_answer(message: str, result: dict) -> str:
    q = message.lower()
    stage = "submission" if "submission" in q else ("approval" if "approval" in q else ("traffic" if "traffic" in q else "disbursement"))
    rows = fm.rows()
    row_by_month = {r["month"]: r for r in rows}
    apr = row_by_month.get("2026-04")
    may = row_by_month.get("2026-05")
    if stage == "submission" and apr and may:
        delta = round((may.get("submission_rate_pct") or 0) - (apr.get("submission_rate_pct") or 0), 1)
        return (
            "Submission had already been identified as an issue in April, but this demo does **not yet have closed-loop outcome tracking** that proves which investigation fixed or failed to fix it.\n\n"
            f"What the data shows: April Submission rate was **{apr['submission_rate_pct']}%** vs 30.0% target; May fell to **{may['submission_rate_pct']}%** (**{delta:+.1f}pp**). "
            "That means the issue persisted into May rather than being fully recovered.\n\n"
            "What Watchtower can do now: use `/jira flag the drops and assign owners to investigate` to create/update the Submission recovery task and default it to the Submission stage owner. "
            "What is still missing as a product feature: after the Jira task is completed, Watchtower should compare before/after metrics and mark the initiative as worked / partially worked / inconclusive."
        )
    return (
        "I can show the metric trend and Jira recovery work, but this demo does not yet store closed-loop investigation outcomes for that stage. "
        "Use `/metrics compare April and May performance` for the trend and `/jira what is critical or off track right now?` for current recovery work."
    )


def _is_epic_assignment_question(message: str) -> bool:
    q = message.lower()
    return ("epic" in q and any(k in q for k in ["unassigned", "assigned", "assign", "assignee"]))


def _render_epic_assignment_answer(result: dict) -> str:
    return (
        "Yes. The Jira Epic issue itself **can** be assigned, but Watchtower separates two concepts:\n\n"
        "- **Jira Epic assignee:** the assignee field on the Epic ticket itself. In the demo this may be Unassigned.\n"
        "- **Operational stage owner:** inferred from owner labels / assignees on open work under that Epic. This is what Watchtower uses when defaulting Jira investigation assignees.\n\n"
        "For the demo, keeping Epic issues unassigned is acceptable because ownership is demonstrated at the stage/task layer. If you want cleaner Jira hygiene, assign each Epic to its operational stage owner:\n\n"
        "| Epic / Stage | Suggested default owner |\n|---|---|\n"
        "| Traffic | Dat Nguyen |\n| Submission | Rino Tran |\n| Approval | bichtram |\n| Disbursement | Dat Nguyen |\n| Data & Platform | Dat Nguyen |\n\n"
        "Demo explanation: **Epic → stage owner → task assignee**. If `/jira create` or `/jira flag` does not mention an assignee, Funnel Agent defaults to the operational stage owner."
    )

def _is_unassigned_work_question(message: str) -> bool:
    q = message.lower()
    return any(k in q for k in [
        "unassigned", "without assignee", "no assignee", "not assigned",
        "without owner", "no owner", "owner unassigned", "assignee unassigned",
    ]) and any(k in q for k in ["task", "tasks", "issue", "issues", "ticket", "tickets", "open", "work"])


def _is_epic_owner_question(message: str) -> bool:
    q = message.lower()
    return ("owner" in q or "owns" in q) and any(k in q for k in ["epic", "epics", "stage", "stages"])


def _render_epic_owner_answer(result: dict) -> str:
    stage_owners = result.get("stage_owners") or {}
    by_epic = result.get("by_epic") or {}
    stage_labels = [
        ("traffic", "Traffic"),
        ("submission", "Submission"),
        ("approval", "Approval"),
        ("completion", "Disbursement"),
        ("crosscut", "Data & Platform"),
    ]
    lines = [
        "Watchtower uses an **Epic → stage owner → task assignee** structure.",
        "",
        "- Each funnel stage has a Jira Epic: Traffic, Submission, Approval, Disbursement, and Data & Platform.",
        "- The Jira Epic issue itself may be unassigned.",
        "- The **operational stage owner** is inferred from owner labels / assignees on open work under that stage.",
        "- When `/jira create ...` or `/jira flag ...` does not name an assignee, Watchtower defaults to the operational stage owner instead of leaving the task unassigned.",
        "",
        "Current operational stage owners:",
        "",
    ]
    for stage, label in stage_labels:
        owner = stage_owners.get(stage) or "Unassigned"
        open_count = (by_epic.get(label) or {}).get("open")
        suffix = f" — {open_count} open item(s)" if open_count is not None else ""
        lines.append(f"- **{label}:** {owner}{suffix}")
    lines += [
        "",
        "So if you ask `who owns Approval`, use the operational owner above. If you want literal Jira Epic assignees, those can still be Unassigned in the demo workspace.",
        "Demo tip: show this before the Jira write step so viewers understand why Watchtower can default the assignee safely.",
    ]
    return "\n".join(lines)


def _fmt_issue_line(issue: dict) -> str:
    key = issue.get("key") or "(no key)"
    summary = issue.get("summary") or "(no summary)"
    stage = issue.get("stage") or issue.get("epic") or "unsorted"
    status = issue.get("status") or "unknown status"
    due = issue.get("due") or "no due date"
    assignee = issue.get("assignee") or "Unassigned"
    owner = issue.get("owner") or "Unassigned"
    details = []
    if owner != "Unassigned" and owner != assignee:
        details.append(f"owner {owner}")
    details.extend([f"assignee {assignee}", f"stage {stage}", f"status {status}", f"due {due}"])
    return f"- {key}: {summary} — " + ", ".join(details)


def _render_unassigned_work_answer(result: dict) -> str:
    owner_items = result.get("owner_unassigned_open") or []
    assignee_items = result.get("assignee_unassigned_open") or []
    # The old LLM answer only had aggregate by_owner counts. Keep both lists so
    # users can distinguish Watchtower's owner mapping from raw Jira assignee.
    items = owner_items or assignee_items
    basis = "Watchtower owner mapping" if owner_items else "real Jira assignee"
    if not items:
        return "I do not see any open UW issues without an owner or Jira assignee right now."
    lines = [
        f"These are the **{len(items)} open issue(s)** without a {basis}:",
        "",
    ]
    for issue in items[:25]:
        lines.append(_fmt_issue_line(issue))
    if len(items) > 25:
        lines.append(f"- …and {len(items) - 25} more.")
    if owner_items and assignee_items and len(owner_items) != len(assignee_items):
        lines += [
            "",
            f"Note: **{len(owner_items)}** are unassigned by Watchtower owner mapping; **{len(assignee_items)}** have no real Jira assignee. "
            "Watchtower treats an `owner-*` label or Jira assignee as the owner signal.",
        ]
    return "\n".join(lines)


def _render_top_risk_answer(result: dict, month: str | None = None) -> str:
    ranking = (result.get("impact_ranking") or {}).get("ranking") or []
    if not ranking:
        return "I do not have enough impact-ranking data to identify a top funnel risk right now."
    top = ranking[0]
    stage = str(top.get("stage", "unknown")).title()
    owner = top.get("owner") or "Unassigned"
    reasons = top.get("reasons") or []
    signal = "; ".join(reasons) if reasons else "target gap / MoM movement"
    risk = top.get("value_at_risk_display") or im.fmt_vnd(top.get("estimated_value_at_risk_vnd"))
    er = top.get("execution_risk") or {}
    execution = ", ".join(er.get("reasons", [])) if isinstance(er, dict) else str(er)
    execution = execution or "no Jira execution risk detected"
    score = top.get("score")
    prefix = f"As of **{month}**, " if month else ""
    lines = [
        f"{prefix}**{stage} is the top risk** because it combines the largest business impact with a material funnel signal.",
        "",
        f"- **Signal:** {signal}",
        f"- **Estimated value at risk:** {risk}",
        f"- **Owner:** {owner}",
        f"- **Execution context:** {execution}",
    ]
    if score is not None:
        lines.append(f"- **Ranking score:** {score}")
    diag_month = _month_name_for_prompt(month) if month else "May"
    stage_prompt = stage.lower()
    lines += [
        "",
        f"This is an impact ranking, not a causal claim. Use `/query break {diag_month} {stage_prompt} drop down by reason` or `/query why did {stage_prompt} drop?` for diagnostic evidence.",
    ]
    return "\n".join(lines)


_MONTH_WORDS = {name.lower(): idx for idx, name in enumerate(calendar.month_name) if name}
_MONTH_WORDS.update({name.lower(): idx for idx, name in enumerate(calendar.month_abbr) if name})


def _month_name_for_prompt(month: str | None) -> str:
    if not month:
        return "May"
    try:
        mo = int(str(month).split("-", 1)[1])
        return calendar.month_name[mo]
    except Exception:  # noqa: BLE001
        return str(month)


def _comparison_months_from_message(message: str) -> list[str] | None:
    """Return two YYYY-MM strings for explicit month-comparison prompts.

    The regular metrics answer is latest-month oriented. This guard prevents a
    prompt like "compare March and April" from incorrectly answering with May.
    """
    q = message.lower()
    if not any(k in q for k in ["compare", "comparison", "mom", "month over month", "month-over-month", " vs ", " versus ", "between"]):
        return None
    year_m = re.search(r"\b(20\d{2})\b", q)
    default_year = int(year_m.group(1)) if year_m else 2026
    found: list[tuple[int, str]] = []
    for m in re.finditer(r"\b(20\d{2})-(\d{1,2})\b", q):
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            found.append((m.start(), f"{y}-{mo:02d}"))
    for name, num in _MONTH_WORDS.items():
        for m in re.finditer(rf"\b{re.escape(name)}\b", q):
            found.append((m.start(), f"{default_year}-{num:02d}"))
    ordered: list[str] = []
    for _, month in sorted(found, key=lambda x: x[0]):
        if month not in ordered:
            ordered.append(month)
    if len(ordered) >= 2:
        return ordered[:2]
    return None


def _month_comparison_result(months: list[str], route_info: dict | None = None) -> dict:
    rows_by_month = {r["month"]: r for r in fm.rows()}
    available = sorted(rows_by_month)
    selected = [m for m in months if m in rows_by_month]
    result = {"requested_months": months, "available_months": available, "route": route_info or {}}
    if len(selected) < 2:
        result["error"] = "Requested months are not both available in the demo dataset."
        return result
    prev, curr = rows_by_month[selected[0]], rows_by_month[selected[1]]
    targets = fm.targets()
    rate_defs = [
        ("submission_rate_pct", "Submission", "submission_rate_pct"),
        ("approval_rate_pct", "Approval", "approval_rate_pct"),
        ("completion_rate_pct", "Disbursement", "completion_rate_pct"),
        ("e2e_rate_pct", "Traffic E2E", "e2e_rate_pct"),
    ]
    rates = []
    critical = []
    for key, label, target_key in rate_defs:
        a, b = prev.get(key), curr.get(key)
        delta = round((b or 0) - (a or 0), 1) if a is not None and b is not None else None
        target = targets.get(target_key)
        status = ""
        if target is not None and b is not None and b < target:
            status = f"below {target}% target"
            critical.append({"metric": label, "current_pct": b, "target_pct": target, "delta_pp": delta, "reason": status})
        elif target is not None and b is not None:
            status = f"meets {target}% target"
        rates.append({"metric": label, "from_pct": a, "to_pct": b, "delta_pp": delta, "target_pct": target, "status": status})
    volumes = []
    for key, label in [("traffic", "Traffic"), ("submission", "Submission"), ("approval", "Approval"), ("completion", "Disbursement")]:
        a, b = prev.get(key), curr.get(key)
        volumes.append({"metric": label, "from": a, "to": b, "delta": (b or 0) - (a or 0)})
    result.update({"from_month": selected[0], "to_month": selected[1], "from": prev, "to": curr,
                   "rates": rates, "volumes": volumes, "critical": critical, "targets": targets})
    return result


def _render_month_comparison_answer(result: dict) -> str:
    if result.get("error"):
        avail = ", ".join(result.get("available_months", []))
        return f"I couldn't compare those months: {result['error']} Available months: {avail}."
    fm0, fm1 = result["from_month"], result["to_month"]
    lines = [f"**MoM comparison: {fm0} → {fm1}**", ""]
    lines += ["**Conversion-rate changes**", "", "| Metric | " + fm0 + " | " + fm1 + " | Change | Target status |", "|---|---:|---:|---:|---|"]
    for r in result["rates"]:
        lines.append(f"| {r['metric']} | {r['from_pct']}% | {r['to_pct']}% | {r['delta_pp']:+.1f}pp | {r['status']} |")
    lines += ["", "**Volume changes**", "", "| Metric | " + fm0 + " | " + fm1 + " | Change |", "|---|---:|---:|---:|"]
    for v in result["volumes"]:
        lines.append(f"| {v['metric']} | {v['from']:,} | {v['to']:,} | {v['delta']:+,} |")
    crit = result.get("critical") or []
    lines += ["", "**Critical readout**"]
    if crit:
        # Lead with non-E2E stage misses before aggregate E2E.
        ordered = sorted(crit, key=lambda x: 1 if x["metric"] == "Traffic E2E" else 0)
        for c in ordered:
            lines.append(f"- **{c['metric']}** is {c['current_pct']}% vs {c['target_pct']}% target ({c['delta_pp']:+.1f}pp vs {fm0}).")
    else:
        lines.append("- No compared rate is below its configured target in the target month.")
    lines.append("- This comparison answers the requested months only; use `show me the funnel metrics` for the latest May risk ranking.")
    return "\n".join(lines)



def _handle_weekly(message: str, lang: str, route_info: dict) -> dict:
    pack = bf.weekly_meeting_pack()
    pack["route"] = route_info
    publish = any(k in message.lower() for k in ["publish", "post", "save", "create page", "write to confluence", "post to confluence"])

    # Use the deterministic weekly summary as the canonical meeting artifact.
    # This keeps Confluence pages stable and prevents the LLM from changing
    # formatting, issue counts, or value-at-risk wording between runs.
    page_body = bf.render_weekly_summary(pack)
    result = dict(pack)
    if publish:
        if not ALLOW_WRITES:
            answer = "I drafted the weekly summary, but writes are off so I did not publish it to Confluence."
            result["published"] = False
            result["publish_error"] = "ALLOW_WRITES=false"
        else:
            page = cf.upsert_page(cf.weekly_title(pack.get("as_of")), page_body)
            result["confluence_page"] = page
            result["published"] = bool(page.get("id"))
            if page.get("url"):
                answer = (
                    f"Published/updated the weekly summary in Confluence: {page['url']}\n\n"
                    "Included: impact-ranked risks, Jira blockers, recently completed work, "
                    "Confluence context, and the recommended weekly agenda."
                )
            else:
                answer = f"Could not publish to Confluence ({page.get('error', 'unknown error')})."
    else:
        answer = page_body
    return _respond("weekly", answer, result)


def _handle_teams(message: str, route_info: dict) -> dict:
    """Interactive Jira -> Teams digest.

    Prompt examples:
    - post off-track blockers to Teams
    - send blocked work to Teams
    - send overdue tasks to Teams
    - send due-soon tasks to Teams
    """
    q = message.lower()
    mode = "off-track"
    title = "Funnel Agent: off-track work"
    empty = "No blocked or overdue open items right now."
    accent = "Attention"

    try:
        if "due" in q and "soon" in q:
            mode = "due-soon"
            issues = jc.due_tomorrow_issues()
            title = "Funnel Agent: due-soon work"
            empty = "No due-soon open items right now."
            accent = "Warning"
            digest = {"route": route_info, "source": "jira_due_tomorrow"}
        elif "overdue" in q:
            mode = "overdue"
            issues = jc.overdue_issues()
            title = "Funnel Agent: overdue work"
            empty = "No overdue open items right now."
            digest = {"route": route_info, "source": "jira_overdue"}
        elif "blocked" in q:
            mode = "blocked"
            issues = jc.blocked_issues()
            title = "Funnel Agent: blocked work"
            empty = "No blocked open items right now."
            digest = {"route": route_info, "source": "jira_blocked"}
        else:
            digest = bf.manager_digest()
            digest["route"] = route_info
            issues = digest.get("needs_attention_now") or []
    except Exception as e:  # noqa: BLE001
        issues = []
        digest = {"route": route_info, "jira_error": type(e).__name__ + ": " + str(e)[:180]}

    sent = False
    reason = None
    if not ALLOW_WRITES:
        reason = "ALLOW_WRITES=false"
    elif not tc.configured():
        reason = "TEAMS_WEBHOOK_URL is not configured"
    else:
        sent = tc.digest_card(title, issues, empty_msg=empty, accent=accent)
        if not sent:
            reason = "Teams webhook call returned false"

    lines = []
    if sent:
        lines.append(f"Posted {len(issues)} {mode} item(s) to Teams.")
    else:
        lines.append(f"I prepared the {mode} Teams reminder but did not post it ({reason}).")
    if digest.get("jira_error"):
        lines.append(f"Jira preview was unavailable: `{digest['jira_error']}`")
    elif issues:
        lines.append("")
        lines.append("Preview:")
        for it in issues[:8]:
            key = it.get("key")
            owner = it.get("owner") or it.get("assignee") or "Unassigned"
            due = it.get("due") or "no due date"
            status = it.get("status") or "unknown status"
            lines.append(f"- {key}: {it.get('summary')} — owner {owner}, status {status}, due {due}")
            blocked_by = it.get("blocked_by")
            blocks = it.get("blocks")
            if blocked_by or blocks:
                lines.append(f"  - Blocker context: blocked by {blocked_by or 'unspecified'}; blocks {blocks or 'unspecified'}")
    else:
        lines.append(empty)
    return _respond("teams", "\n".join(lines), {"mode": mode, "sent": sent, "reason": reason, "issues": issues, "teams_configured": tc.configured(), **digest})


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
        owner = owners.get(stage) or risk.get("owner") or _default_owner_for_stage(stage)
        if owner == "Unassigned":
            owner = _default_owner_for_stage(stage)
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
            assignee_display = None
            assignment_note = ""
            if owner:
                try:
                    user = jc.find_assignable_user(owner)
                    if user:
                        assignee_id = user["accountId"]
                        assignee_display = user.get("displayName")
                except Exception:  # noqa: BLE001
                    assignee_id = None
                assignment_note = _default_owner_note(stage, owner, assignee_display)
            existing = None
            try:
                existing = jc.find_open_investigation(stage, metric=metric, month=str(month))
            except Exception:  # noqa: BLE001
                existing = None
            if existing:
                try:
                    jc.comment_issue(existing["key"], "Funnel Agent refreshed this investigation.\n\n" + description)
                except Exception:  # noqa: BLE001
                    pass
                if owner:
                    try:
                        jc.assign_issue(existing["key"], assignee_id=assignee_id, owner=owner)
                    except Exception:  # noqa: BLE001
                        pass
                line += f" → updated existing {existing['key']}"
                if assignment_note:
                    line += f"; {assignment_note}"
                actions.append({"stage": stage, "action": "updated", "key": existing["key"], "contract": contract, "default_owner": owner, "assignee_id": assignee_id})
            else:
                epic_name = STAGE_TO_EPIC.get(stage)
                try:
                    epic_key = jc.find_epic(epic_name) if epic_name else None
                except Exception:  # noqa: BLE001
                    epic_key = None
                title = f"Investigate {stage.title()}: " + "; ".join(why)
                res = jc.create_issue(summary=title, stage=stage, owner=owner, due=None,
                                      assignee_id=assignee_id, epic_key=epic_key,
                                      labels_extra=labels_extra, description=description)
                if res.get("key"):
                    line += f" → opened {res['key']}"
                    if assignment_note:
                        line += f"; {assignment_note}"
                    actions.append({"stage": stage, "action": "created", "key": res["key"], "contract": contract, "default_owner": owner, "assignee_id": assignee_id})
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
        stage = f.get("stage")
        explicit_owner = f.get("owner")
        owner = explicit_owner or _default_owner_for_stage(stage)
        if owner and not f.get("owner"):
            f["owner"] = owner
            f.setdefault("evidence", [])
            if isinstance(f["evidence"], list):
                f["evidence"].append("No assignee was mentioned; Watchtower defaulted to the operational stage owner.")
        assignee_id = None
        assign_note = ""
        if owner:
            user = jc.find_assignable_user(owner)
            if user:
                assignee_id = user["accountId"]
                if explicit_owner:
                    assign_note = f"assigned to {user['displayName']}"
                else:
                    assign_note = _default_owner_note(stage, owner, user.get("displayName"))
            else:
                if explicit_owner:
                    assign_note = f"tagged {jc.owner_label(owner)}"
                else:
                    assign_note = _default_owner_note(stage, owner) + f" Owner label `{jc.owner_label(owner)}` stamped because Jira did not return a matching assignable user."
        else:
            me = jc.myself()
            if me:
                assignee_id = me["accountId"]
                assign_note = f"No stage owner could be inferred; assigned to you ({me['displayName']})"

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
    if isinstance(answer, str):
        route = result.get("route") if isinstance(result, dict) else None
        warning = (route or {}).get("warning") if isinstance(route, dict) else None
        if warning and not result.get("prefix_required") and not result.get("clarification_required"):
            answer = f"> ⚠️ **Routing note:** {warning}\n\n" + answer
        answer = jc.link_issue_keys(answer)
    return {
        "status": "success",
        "intent": intent,
        "answer": answer,
        "result": result,
        "version": BUILD_VERSION,
        "app_version": APP_VERSION,
        "disclaimer": "Synthetic workspace data — Claw-a-thon 2026 demo.",
        "timestamp": datetime.now().isoformat(),
    }


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
