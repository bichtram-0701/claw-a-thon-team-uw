"""Semantic intent router for Funnel Watchtower.

LLM-first routing fixes brittle keyword collisions such as "daily volume" being
mistaken for "standup". Keywords remain as an offline fallback and as validation
signals for high-risk write intents.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re

import report as rp

VALID = {
    "create", "assign", "flag", "analyst", "metrics", "oversight", "briefing",
    "sprint", "knowledge", "standup", "weekly", "teams", "help",
}

ROUTES: list[tuple[set[str], str]] = [
    ({"help", "how to use", "how should i ask", "how should i use", "guide", "usage", "instructions",
      "what can you do", "prompt examples", "demo prompts"}, "help"),
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
    ({"metric", "conversion", "submission rate", "approval rate", "completion rate", "traffic",
      "ticket size", "funnel performance", "funnel numbers", "funnel table", "performance", "e2e",
      "throughput", "how is the funnel doing", "compare", "comparison", "what changed",
      "concerning", "drop", "dropped", "month over month", "mom", "vs last month", "anomal",
      "value at risk", "impact ranking", "business risk", "top risk", "top recovery", "recovery priority",
      "prioritize", "rank"}, "metrics"),
    ({"oversight", "overview", "funnel", "digest", "who is working", "who's working", "who owns",
      "ownership", "on track", "off track", "off-track", "critical", "at risk", "behind", "slipping",
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
        "You route messages for Funnel Watchtower, a business-funnel execution assistant. "
        "Return STRICT JSON only with keys: intent, confidence, reason. "
        "intent must be exactly one of: create, assign, flag, analyst, metrics, oversight, briefing, sprint, knowledge, standup, weekly, teams, help.\n"
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




def _explicit_help_signal(message: str) -> bool:
    msg = message.lower()
    return any(k in msg for k in [
        "how to use", "how should i ask", "how should i use", "usage",
        "instructions", "prompt examples", "demo prompts", "what can you do"
    ])


def _explicit_blocker_explanation_signal(message: str) -> bool:
    """Route blocker semantics to Jira execution context, not the generic usage guide."""
    msg = message.lower()
    if "blocked" not in msg and "blocking" not in msg:
        return False
    return any(k in msg for k in [
        "what does blocked mean", "what is blocked", "what's blocked",
        "what is it blocking", "what's it blocking", "what does it block",
        "what is blocking", "blocked mean", "blocker context", "blocking?",
    ])


def _explicit_unassigned_signal(message: str) -> bool:
    """Route requests for unassigned work to Jira execution context."""
    msg = message.lower()
    return any(k in msg for k in [
        "unassigned", "without assignee", "no assignee", "not assigned",
        "without owner", "no owner", "owner unassigned", "assignee unassigned",
    ]) and any(k in msg for k in ["task", "tasks", "issue", "issues", "ticket", "tickets", "open", "work"])


def route_result(message: str) -> RouteResult:
    fallback = keyword_route(message)
    if _explicit_unassigned_signal(message):
        return RouteResult("oversight", "keyword", 1.0, fallback, "explicit unassigned-work prompt")
    if _explicit_blocker_explanation_signal(message):
        return RouteResult("oversight", "keyword", 1.0, fallback, "explicit blocker explanation prompt")
    if _explicit_help_signal(message):
        return RouteResult("help", "keyword", 1.0, fallback, "explicit usage/help prompt")
    llm_intent, confidence, reason = _llm_route(message)
    if llm_intent and confidence >= 0.45:
        validated, correction = _validate(llm_intent, message, fallback)
        if validated == "help" and fallback != "help":
            return RouteResult(fallback, "llm+guard", confidence, fallback, "corrected help->fallback for workflow-specific prompt")
        return RouteResult(validated, "llm" if not correction else "llm+guard", confidence, fallback, correction or reason)
    return RouteResult(fallback, "keyword", 1.0 if fallback != "help" else 0.0, fallback, reason)


def route(message: str) -> str:
    return route_result(message).intent


def trace(message: str) -> dict:
    return asdict(route_result(message))
