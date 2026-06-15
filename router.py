"""Command-aware semantic router for Funnel Agent.

Reliability rule:
- Slash-command prompts route deterministically: /metrics, /jira, /confluence, /teams, /help, /model. (/query is kept as an alias for metric/data drilldowns.)
- Legacy colon prefixes (metrics:, sql:, jira:, confluence:, teams:, help:) are still accepted as aliases.
- Non-prefixed read-only prompts are still supported in warn mode, but the answer
  gets an interpretation warning.
- Non-prefixed write prompts are blocked in warn/strict mode and ask the user to
  resend with the right prefix.

This turns the bot from a free-form chatbot into a workflow router with explicit
contracts for data, Jira, Confluence, and Teams actions.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import os
import re

import report as rp

VALID = {
    "create", "assign", "flag", "analyst", "metrics", "oversight", "briefing",
    "sprint", "knowledge", "standup", "weekly", "teams", "help", "model",
}

PREFIX_TO_SYSTEM = {
    "metrics": "metrics",
    "query": "analyst",
    "sql": "analyst",
    "data": "analyst",
    "jira": "jira",
    "confluence": "confluence",
    "teams": "teams",
    "help": "help",
    "model": "model",
}

# Preferred user syntax is slash-command style. Colon prefixes are accepted as
# backwards-compatible aliases so old demo prompts do not break.
COMMAND_PREFIX_RE = re.compile(
    r"^\s*(?:/(metrics|query|sql|data|jira|confluence|teams|help|model)|"
    r"(metrics|query|sql|data|jira|confluence|teams|help|model)\s*:)\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

ROUTES: list[tuple[set[str], str]] = [
    ({"help", "how to use", "how should i ask", "how should i use", "guide", "usage", "instructions",
      "what can you do", "prompt examples", "demo prompts", "command", "commands", "prefix", "what model", "which model", "model are you",
      "difference between metrics", "metrics and sql", "metrics vs sql", "metrics and query",
      "metrics vs query", "what is metrics", "what is query"}, "help"),
    ({"teams", "microsoft teams", "post to teams", "send to teams", "notify teams",
      "remind on teams", "remind in teams", "teams reminder", "post off-track blockers to teams", "post off-track", "send the off-track work to teams",
      "send off-track work to teams", "send overdue", "remind of overdue"}, "teams"),
    ({"weekly", "week in review", "weekly meeting", "meeting summary", "meeting notes",
      "recap everything", "summarize everything", "summarise everything", "post to confluence",
      "save to confluence", "weekly readout", "weekly agenda"}, "weekly"),
    ({"flag", "investigate", "open investigation", "open an investigation", "raise an investigation",
      "look into the drop"}, "flag"),
    ({"create ", "create a", "add ticket", "add a ticket", "new ticket", "new initiative",
      "open a ticket", "file a ticket", "log a ticket"}, "create"),
    ({"assign ", "re-assign", "reassign "}, "assign"),
    ({"standup", "stand-up", "stand up", "yesterday / today / blockers", "yesterday today blockers"}, "standup"),
    ({"decide", "decision", "decided", "document", "wiki", "confluence", "wrote"}, "knowledge"),
    ({"plate", "my task", "my issue", "my initiative", "assigned to me", "what should i"}, "briefing"),
    ({"by day", "day by day", "per day", "daily", "day over day", "day-over-day", "by week", "per week", "by product",
      "per product", "by channel", "per channel", "by drop", "drop reason", "break down", "breakdown",
      "group by", "by segment", "slice", "each day", "by month per", "daily volume", "volume by", "count by",
      "why did", "root cause", "diagnose", "diagnostic", "driver", "contribution", "what caused", "approval drop", "approval fell"},
     "analyst"),
    ({"metric", "conversion", "submission rate", "approval rate", "disbursement rate", "traffic",
      "ticket size", "funnel performance", "funnel numbers", "funnel table", "performance", "e2e",
      "throughput", "how is the funnel doing", "compare", "comparison", "what changed",
      "concerning", "drop", "dropped", "month over month", "mom", "vs last month", "anomal",
      "value at risk", "impact ranking", "business risk", "top risk", "top recovery", "recovery priority",
      "prioritize", "rank"}, "metrics"),
    ({"oversight", "overview", "funnel", "digest", "who is working", "who's working", "who owns",
      "ownership", "owner of each epic", "epic owner", "epic owners", "who owns each epic", "who owns every epic", "on track", "off track", "off-track", "critical", "at risk", "behind", "slipping",
      "unassigned", "without assignee", "no assignee", "not assigned", "without owner", "no owner",
      "manager", "lead", "report", "status of"},
     "oversight"),
    ({"sprint", "team", "pulse", "progress", "stuck", "blocked", "workload", "overdue"},
     "sprint"),
]


@dataclass
class RouteResult:
    intent: str
    source: str
    confidence: float
    fallback_intent: str
    reason: str = ""
    prefix: str | None = None
    stripped_message: str | None = None
    warning: str | None = None
    needs_prefix: bool = False
    needs_clarification: bool = False
    clarification: str | None = None
    interpreted_as: str | None = None


def routing_mode() -> str:
    return os.environ.get("ROUTING_MODE", "warn").strip().lower() or "warn"


def _normalize_prefix(prefix: str | None) -> str | None:
    if not prefix:
        return None
    p = prefix.lower().strip()
    if p in {"sql", "data"}:
        return "query"
    return p


def parse_prefix(message: str) -> tuple[str | None, str]:
    m = COMMAND_PREFIX_RE.match(message or "")
    if not m:
        return None, message
    prefix = _normalize_prefix(m.group(1) or m.group(2))
    return prefix, (m.group(3) or "").strip()


def command_text(prefix: str | None, message: str = "") -> str:
    p = _normalize_prefix(prefix) or "help"
    return (f"/{p} {message}" if message else f"/{p}").strip()


def keyword_route(message: str) -> str:
    msg = message.lower()
    for keywords, intent in ROUTES:
        if any(k in msg for k in keywords):
            return intent
    return "help"


def _one_line(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.strip().splitlines()[0].strip()


def _llm_route(message: str) -> tuple[str | None, float, str]:
    raw = rp.llm_chat(
        "You route messages for Funnel Agent, a business-funnel execution assistant. "
        "Return STRICT JSON only with keys: intent, confidence, reason. "
        "intent must be exactly one of: create, assign, flag, analyst, metrics, oversight, briefing, sprint, knowledge, standup, weekly, teams, help, model.\n"
        "Definitions:\n"
        "- analyst = ad-hoc application data query/breakdown/count/volume by day/week/product/channel/drop reason.\n"
        "- metrics = standard funnel performance, conversion, target miss, value-at-risk/impact ranking.\n"
        "- oversight = manager view of Jira initiatives: ownership, blockers, off-track, critical.\n"
        "- weekly = weekly meeting readout/summary/agenda/recap of everything, optionally posted to Confluence.\n"
        "- teams = send/post/notify Microsoft Teams with overdue, blocked, off-track, or due-soon Jira work.\n"
        "Important: 'daily volume' or 'daily approval volume' is analyst, not standup. Do not choose standup unless the user explicitly asks for standup or Yesterday/Today/Blockers. Default to English for ambiguous prompts.",
        message,
        max_tokens=220,
        temperature=0.0,
        profile="classifier",
    )
    obj = rp.extract_json_object(raw)
    if obj:
        intent = str(obj.get("intent", "")).strip().lower()
        try:
            conf = float(obj.get("confidence", 0.0))
        except Exception:  # noqa: BLE001
            conf = 0.0
        reason = str(obj.get("reason", ""))[:180]
        if intent in VALID:
            return intent, max(0.0, min(1.0, conf)), reason
    word = _one_line(raw)
    if word:
        word = word.lower().split()[0].strip(".,!\"'`")
        if word in VALID:
            return word, 0.65, "one-word fallback"
    return None, 0.0, "llm unavailable or invalid"


def _validate(intent: str, message: str, fallback: str) -> tuple[str, str]:
    msg = message.lower()
    has_issue_key = bool(re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", message))
    standup_signal = any(k in msg for k in ["standup", "stand-up", "stand up", "yesterday", "blockers"])
    analyst_signal = any(k in msg for k in ["daily", "volume", "day over day", "day-over-day", "by day", "by product", "by channel", "drop reason", "breakdown", "break down", "group by"])
    diagnostic_signal = any(k in msg for k in ["why", "root cause", "diagnose", "diagnostic", "driver", "contribution", "what caused"]) and any(k in msg for k in ["drop", "dropped", "down", "fell", "below", "miss"]) and any(k in msg for k in ["submission", "approval", "completion", "traffic"])
    create_signal = any(k in msg for k in ["create", "add ticket", "new ticket", "open a ticket", "file a ticket", "log a ticket", "new initiative"])
    assign_signal = any(k in msg for k in ["assign ", "reassign", "re-assign", "giao", "gan"])
    blocker_followup = (
        ("blocked" in msg or "blocking" in msg)
        and any(k in msg for k in ["what does", "mean", "meaning", "what is it blocking", "what does it block", "blocks", "blocked by", "why blocked"])
    )

    if intent == "help" and blocker_followup:
        return "oversight", "corrected help->oversight because the message asks about blocker context"
    if intent == "standup" and not standup_signal and analyst_signal:
        return "analyst", "corrected standup->analyst because the message asks for volume/breakdown"
    if intent == "metrics" and diagnostic_signal:
        return "analyst", "corrected metrics->analyst because the message asks for a stage-drop diagnostic"
    if intent == "create" and not create_signal:
        return fallback if fallback != "help" else "help", "blocked create without create/ticket signal"
    if intent == "assign" and not (assign_signal and has_issue_key):
        if "assigned to me" in msg or "my task" in msg or "my plate" in msg:
            return "briefing", "corrected assign->briefing for personal task query"
        return fallback if fallback != "help" else "help", "blocked assign without issue key + assign signal"
    return intent, ""


def _explicit_model_signal(message: str) -> bool:
    msg = message.lower().strip()
    return msg in {"/model", "model"} or any(k in msg for k in [
        "what model are you using", "which model are you using", "what chatbot model",
        "what chat model", "which llm", "what llm", "model am i talking to",
        "what model am i talking to", "are you using gpt", "are you using qwen",
    ])


def _explicit_help_signal(message: str) -> bool:
    msg = message.lower()
    return any(k in msg for k in [
        "how to use", "how should i ask", "how should i use", "usage",
        "instructions", "prompt examples", "demo prompts", "what can you do",
        "difference between metrics", "metrics and sql", "metrics vs sql",
        "metrics and query", "metrics vs query", "what is metrics", "what is query",
        "slash command", "commands", "prefix", "what model", "which model", "model are you",
    ])


def _explicit_blocker_explanation_signal(message: str) -> bool:
    msg = message.lower()
    if "blocked" not in msg and "blocking" not in msg:
        return False
    return any(k in msg for k in [
        "what does blocked mean", "what is blocked", "what's blocked",
        "what is it blocking", "what's it blocking", "what does it block",
        "what is blocking", "blocked mean", "blocker context", "blocking?",
    ])


def _explicit_epic_owner_signal(message: str) -> bool:
    msg = message.lower()
    return ("epic" in msg or "epics" in msg or "stage" in msg or "stages" in msg) and any(k in msg for k in [
        "owner", "owners", "owns", "ownership", "who owns", "who's the owner", "who is the owner"
    ])


def _explicit_unassigned_signal(message: str) -> bool:
    msg = message.lower()
    return any(k in msg for k in [
        "unassigned", "without assignee", "no assignee", "not assigned",
        "without owner", "no owner", "owner unassigned", "assignee unassigned",
    ]) and any(k in msg for k in ["task", "tasks", "issue", "issues", "ticket", "tickets", "open", "work"])


def _explicit_create_signal(message: str) -> bool:
    msg = message.lower()
    return any(k in msg for k in [
        "create a ticket", "create ticket", "open a ticket", "open ticket",
        "file a ticket", "log a ticket", "add a ticket", "new ticket",
        "create an issue", "open an issue", "create a task", "new task",
    ])


def _explicit_assign_signal(message: str) -> bool:
    return bool(re.search(r"\bassign\s+[A-Z][A-Z0-9]+-\d+\s+to\s+", message, flags=re.IGNORECASE))


def _stage_present(message: str) -> bool:
    msg = message.lower()
    return any(k in msg for k in [
        "traffic", "submission", "submit", "submitted", "approval", "approved", "disbursement", "disburse", "disbursed", "completion", "completed",
        "e2e", "end-to-end", "top risk", "top-risk", "current top risk",
    ])


def _needs_clarification(message: str, intent: str) -> str | None:
    msg = message.lower().strip()
    if intent in {"create", "assign", "flag", "teams"}:
        return None
    ambiguous_drop = any(k in msg for k in ["why did it drop", "why is it down", "what caused the drop", "show drop reasons", "show drop reason", "break down drop reasons", "breakdown drop reasons"])
    ambiguous_volume = msg in {"show volume", "what volume", "what's this volume", "volume", "daily"}
    if ambiguous_drop and not _stage_present(msg):
        return (
            "Which funnel transition should I diagnose?\n\n"
            "1. `/metrics break May traffic drop down by reason`\n"
            "2. `/metrics break May approval drop down by reason`\n"
            "3. `/metrics break May disbursement drop down by reason`\n"
            "4. `/metrics why is the current top risk?`"
        )
    if ambiguous_volume:
        return (
            "What volume do you want? For exact routing, try one of these:\n\n"
            "- `/metrics show daily volume in May`\n"
            "- `/metrics show me the funnel metrics`\n"
            "- `/metrics show May volume by channel`"
        )
    return None


def _publish_to_confluence(message: str) -> bool:
    msg = message.lower()
    return any(k in msg for k in ["publish", "post", "save", "create page", "write to confluence", "post to confluence"])


def _write_like(intent: str, message: str) -> bool:
    if intent in {"create", "assign", "flag", "teams"}:
        return True
    if intent == "weekly" and _publish_to_confluence(message):
        return True
    return False


def _prefix_for_intent(intent: str) -> str:
    if intent in {"analyst", "metrics"}:
        return "metrics"
    if intent in {"model"}:
        return "model"
    if intent in {"weekly", "knowledge"}:
        return "confluence"
    if intent in {"teams"}:
        return "teams"
    if intent in {"create", "assign", "flag", "oversight", "briefing", "sprint", "standup"}:
        return "jira"
    return "help"


def _metrics_drilldown_signal(message: str) -> bool:
    msg = message.lower()
    # /metrics is the main user-facing data command. If the prompt asks for a
    # row-level breakdown/table, route to the safe query/template layer.
    return any(k in msg for k in [
        "daily", "day over day", "day-over-day", "by day", "per day",
        "weekly volume", "by week", "per week", "by product", "per product",
        "by channel", "per channel", "drop reason", "drop reasons",
        "break down", "breakdown", "down by reason", "break ", "group by", "slice", "show sql",
        "volume by", "count by", "why did", "root cause", "diagnose",
        "diagnostic", "driver", "contribution", "what caused",
    ]) and not any(k in msg for k in ["top risk", "top recovery", "recovery priority", "value at risk", "funnel metrics", "funnel table"])


def _route_within_metrics(message: str) -> str:
    if _explicit_help_signal(message):
        return "help"
    if _metrics_drilldown_signal(message):
        return "analyst"
    return "metrics"


def _route_within_jira(message: str) -> str:
    msg = message.lower()
    if _explicit_create_signal(message):
        return "create"
    if _explicit_assign_signal(message):
        return "assign"
    if any(k in msg for k in ["flag", "investigate", "open investigation", "assign owners to investigate", "recovery action"]):
        return "flag"
    if _explicit_blocker_explanation_signal(message) or _explicit_epic_owner_signal(message) or _explicit_unassigned_signal(message):
        return "oversight"
    if any(k in msg for k in ["critical", "off track", "off-track", "owner", "who owns", "who is working", "who's working", "overview", "blocked", "blocking", "overdue"]):
        return "oversight"
    if any(k in msg for k in ["standup", "stand-up", "stand up"]):
        return "standup"
    if any(k in msg for k in ["sprint", "workload", "team pulse"]):
        return "sprint"
    if any(k in msg for k in ["my plate", "assigned to me", "my tasks"]):
        return "briefing"
    return "oversight"


def _route_within_confluence(message: str) -> str:
    msg = message.lower()
    if any(k in msg for k in ["weekly", "meeting", "summary", "agenda", "publish", "post", "save", "recap everything", "summarize everything"]):
        return "weekly"
    if any(k in msg for k in ["decision", "decide", "document", "wiki", "page", "what did we"]):
        return "knowledge"
    return "weekly"


def _explicit_prefix_route(prefix: str, message: str, fallback: str) -> RouteResult:
    p = _normalize_prefix(prefix) or prefix.lower()
    if p in {"query", "sql", "data"}:
        intent = "analyst"
    elif p == "metrics":
        intent = _route_within_metrics(message)
    elif p == "teams":
        intent = "teams"
    elif p == "help":
        intent = "help"
    elif p == "model":
        intent = "model"
    elif p == "jira":
        intent = _route_within_jira(message)
    elif p == "confluence":
        intent = _route_within_confluence(message)
    else:
        intent = fallback
    return RouteResult(
        intent=intent,
        source="prefix",
        confidence=1.0,
        fallback_intent=fallback,
        reason=f"explicit /{p} prefix",
        prefix=p,
        stripped_message=message,
        interpreted_as=command_text(p, message),
    )


def _apply_no_prefix_policy(result: RouteResult, original: str) -> RouteResult:
    mode = routing_mode()
    guessed_prefix = _prefix_for_intent(result.intent)
    interpreted_as = command_text(guessed_prefix, original.strip())
    result.interpreted_as = interpreted_as
    if mode == "natural":
        return result
    if mode == "strict":
        result.intent = "help"
        result.source = "strict_guard"
        result.warning = None
        result.needs_prefix = True
        result.reason = "ROUTING_MODE=strict requires a slash command"
        return result
    # warn mode
    clarification = _needs_clarification(original, result.intent)
    if clarification:
        result.intent = "help"
        result.needs_clarification = True
        result.clarification = clarification
        result.reason = "ambiguous prompt needs clarification"
        return result
    result.warning = (
        "No slash command detected. I interpreted this as "
        f"`{interpreted_as}`. For exact routing, start with one of: "
        "`/metrics`, `/jira`, `/confluence`, `/teams`, `/help`, `/model`."
    )
    if _write_like(result.intent, original):
        result.needs_prefix = True
        result.reason = "write-like prompt requires explicit slash command"
    return result


def route_result(message: str) -> RouteResult:
    original = message or ""
    prefix, stripped = parse_prefix(original)
    fallback = keyword_route(stripped if prefix else original)
    if prefix:
        return _explicit_prefix_route(prefix, stripped, fallback)

    if _explicit_create_signal(original):
        result = RouteResult("create", "keyword", 1.0, fallback, "explicit create-ticket prompt", stripped_message=original)
        return _apply_no_prefix_policy(result, original)
    if _explicit_assign_signal(original):
        result = RouteResult("assign", "keyword", 1.0, fallback, "explicit assign prompt", stripped_message=original)
        return _apply_no_prefix_policy(result, original)
    if _explicit_epic_owner_signal(original):
        result = RouteResult("oversight", "keyword", 1.0, fallback, "explicit epic-owner prompt", stripped_message=original)
        return _apply_no_prefix_policy(result, original)
    if _explicit_unassigned_signal(original):
        result = RouteResult("oversight", "keyword", 1.0, fallback, "explicit unassigned-work prompt", stripped_message=original)
        return _apply_no_prefix_policy(result, original)
    if _explicit_blocker_explanation_signal(original):
        result = RouteResult("oversight", "keyword", 1.0, fallback, "explicit blocker explanation prompt", stripped_message=original)
        return _apply_no_prefix_policy(result, original)
    if _explicit_model_signal(original):
        return RouteResult("model", "keyword", 1.0, fallback, "explicit model-info prompt", stripped_message=original, interpreted_as=command_text("model"))
    if _explicit_help_signal(original):
        # Help itself is safe without a prefix; no warning needed.
        return RouteResult("help", "keyword", 1.0, fallback, "explicit usage/help prompt", stripped_message=original, interpreted_as=command_text("help", original.strip()))

    llm_intent, confidence, reason = _llm_route(original)
    if llm_intent and confidence >= 0.45:
        validated, correction = _validate(llm_intent, original, fallback)
        if validated == "help" and fallback != "help":
            result = RouteResult(fallback, "llm+guard", confidence, fallback, "corrected help->fallback for workflow-specific prompt", stripped_message=original)
        else:
            result = RouteResult(validated, "llm" if not correction else "llm+guard", confidence, fallback, correction or reason, stripped_message=original)
        return _apply_no_prefix_policy(result, original)

    result = RouteResult(fallback, "keyword", 1.0 if fallback != "help" else 0.0, fallback, reason, stripped_message=original)
    return _apply_no_prefix_policy(result, original)


def route(message: str) -> str:
    return route_result(message).intent


def trace(message: str) -> dict:
    return asdict(route_result(message))
