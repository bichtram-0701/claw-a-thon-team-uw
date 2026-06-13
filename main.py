"""Funnel Watchtower — lending-funnel initiative tracker. Team UW, Claw-a-thon 2026.

A line-manager oversight agent over the loan-application funnel. Ask in plain
language (VI/EN): give me the funnel overview, who is working on what, what's
critical / off track, what did we decide about X, what's on my plate, draft my
standup. Deterministic clients fetch the facts from Jira + Confluence; the MaaS
LLM narrates — it never invents data, and every feature degrades gracefully when
Jira/Confluence/LLM are unreachable.

Connected to a FREE Atlassian Cloud workspace seeded with synthetic funnel
initiatives. No company systems, no real personal data.
(The team's earlier lending-analytics agent lives on in git history.)
"""

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from greennode_agentbase import (
    GreenNodeAgentBaseApp,
    PingStatus,
    RequestContext,
)
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from starlette.routing import Route

load_dotenv()

import briefing as bf            # noqa: E402
import confluence_client as cf   # noqa: E402
import jira_client as jc         # noqa: E402
import report as rp              # noqa: E402

# CORS: allow browsers (chat page) to call /invocations.
_middleware = [Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])]
try:  # keep the SDK's own middleware if importable (private API, may move)
    from greennode_agentbase.runtime.app import XAccelBufferingMiddleware
    _middleware.insert(0, Middleware(XAccelBufferingMiddleware))
except ImportError:
    pass

app = GreenNodeAgentBaseApp(middleware=_middleware)

# Serve the chat UI at the endpoint root — same origin, no CORS needed.
_CHAT_PAGE = os.path.join(os.path.dirname(__file__), "chat.html")


async def _serve_chat(request):
    return FileResponse(_CHAT_PAGE, media_type="text/html")


app.router.routes.append(Route("/", _serve_chat, methods=["GET"]))

# ------------------------------------------------------------- intent router
# Keyword matching first (free); LLM classification when keywords miss.

# Order matters: more specific intents first. "standup" before the manager
# keywords (a standup is about the user's own items), then the LM oversight view.
ROUTES = [
    ({"standup", "stand-up", "stand up", "daily"}, "standup"),
    ({"decide", "decision", "decided", "document", "wiki", "confluence", "wrote",
      "quyết định", "quyet dinh", "tài liệu", "tai lieu", "biên bản", "bien ban"}, "knowledge"),
    ({"plate", "my task", "my issue", "my initiative", "assigned to me", "what should i",
      "việc của tôi", "viec cua toi"}, "briefing"),
    ({"oversight", "overview", "funnel", "digest", "who is working", "who's working",
      "who owns", "ownership", "on track", "off track", "off-track", "critical",
      "at risk", "behind", "slipping", "manager", "lead", "report", "status of",
      "ai đang làm", "tổng quan", "quan trọng", "trễ", "rủi ro"}, "oversight"),
    ({"sprint", "team", "pulse", "progress", "stuck", "blocked", "workload", "overdue",
      "tiến độ", "tien do", "nhóm", "nhom"}, "sprint"),
]

VALID = {"oversight", "briefing", "sprint", "knowledge", "standup", "help"}


def route(message: str) -> str:
    msg = message.lower()
    for keywords, intent in ROUTES:
        if any(k in msg for k in keywords):
            return intent
    return rp_classify(message) or "help"


def rp_classify(message: str) -> str | None:
    out = rp.llm_chat(
        "Classify the user's question about a lending-funnel initiative tracker into exactly "
        "one word from: oversight, briefing, sprint, knowledge, standup, help. "
        "oversight = the lead's view of all initiatives: who owns what, what's critical, what's "
        "on/off track, funnel overview; briefing = the user's OWN tasks/priorities; "
        "sprint = simple status mix / workload of the whole team; knowledge = past decisions, "
        "documentation, meeting notes; standup = draft a standup update; help = anything else. "
        "Reply with the single word only.",
        message, max_tokens=64)
    if out:
        word = out.strip().lower().split()[0].strip(".,!")
        if word in VALID:
            return word
    return None


# ---------------------------------------------------------------- entrypoint

NARRATE_SYS = {
    "oversight": "You are briefing the lending lead on the funnel initiatives. Lead with "
                 "'needs_attention_now' (critical AND off track) — name the item, owner and why. "
                 "Then give a short read on each funnel stage and flag any owner who is overloaded "
                 "or carrying off-track work. Quote issue keys and owners. Be decisive and brief; "
                 "if the user asks for a breakdown, use a markdown table.",
    "briefing": "Summarize what's on the user's plate: lead with the most urgent item "
                "(overdue/blocked first), then the rest in priority order. Quote issue keys.",
    "sprint":   "Give a team health summary: open vs done, where work is piling up, "
                "blocked and overdue items with issue keys, who looks overloaded.",
    "knowledge": "Answer the question using ONLY the page contents provided. Quote the "
                 "deciding sentence(s), then cite page title and url. If pages don't "
                 "contain the answer, say so plainly.",
    "standup":  "Write a ready-to-paste standup message with sections Yesterday / Today / "
                "Blockers, using issue keys. Keep it tight and human.",
}


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    try:
        return _handle(payload)
    except Exception as e:  # noqa: BLE001 — never return a bare 500 to the caller
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
    intent = route(message)

    if not jc.configured() and intent != "help":
        return _respond(intent,
                        "I can't reach Jira/Confluence right now (credentials not configured). "
                        "Please tell the team to check the deployment.",
                        {"error": "Atlassian credentials not configured on the runtime"})

    answer = None
    if intent == "oversight":
        result = bf.manager_digest()
    elif intent == "briefing":
        result = bf.my_briefing()
    elif intent == "sprint":
        result = bf.sprint_pulse()
    elif intent == "knowledge":
        result = bf.knowledge(message)
    elif intent == "standup":
        result = bf.standup_draft()
    else:
        result = {"hint": "Try: give me the funnel overview · who is working on what? · "
                          "what's critical or off track? · what did we decide about <topic>? · "
                          "what's on my plate? · draft my standup"}
        answer = (
            "Hi! I'm Funnel Watchtower (Team UW). I track every initiative on the loan "
            "application funnel from our Jira + Confluence. Ask me things like: 'give me the "
            "funnel overview', 'who is working on what?', 'what's critical or off track?', "
            "'what did we decide about docs-upload?', 'what's on my plate?', or 'draft my "
            "standup'. Tiếng Việt cũng được nhé!"
        )

    # LLM narration with intent-specific instructions (deterministic JSON is the truth)
    if answer is None:
        sys_extra = NARRATE_SYS.get(intent, "")
        lang_line = "Answer in Vietnamese." if lang == "vi" else "Answer in the user's language (default English)."
        out = rp.llm_chat(
            "You are Funnel Watchtower, a lending-funnel initiative tracker for the team lead. "
            "Use ONLY the JSON data provided — never invent issues, owners or numbers. " + sys_extra +
            " If the user asks for a table, use a markdown table. " + lang_line,
            "Question: " + message + "\nData JSON:\n" + json.dumps(result, ensure_ascii=False),
            max_tokens=900,
        )
        answer = out or json.dumps(result, ensure_ascii=False, indent=2)

    return _respond(intent, answer, result)


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
