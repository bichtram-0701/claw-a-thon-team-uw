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
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

load_dotenv()

import briefing as bf            # noqa: E402
import confluence_client as cf   # noqa: E402
import funnel_metrics as fm      # noqa: E402
import jira_client as jc         # noqa: E402
import report as rp              # noqa: E402
import teams_client as tc        # noqa: E402

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


# Real-time Jira -> Teams diff. A Jira Automation rule POSTs {"key": "KAN-123"}
# here on issue update; we read the latest changelog (old->new) and post a card.
JIRA_EVENT_TOKEN = os.environ.get("JIRA_EVENT_TOKEN", "")


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

# ------------------------------------------------------------- intent router
# Keyword matching first (free); LLM classification when keywords miss.

ALLOW_WRITES = os.environ.get("ALLOW_WRITES", "true").lower() in ("1", "true", "yes")

# Funnel stage -> Epic name (the Epic is the swimlane / project a task lives under)
STAGE_TO_EPIC = {
    "traffic": "Traffic", "submission": "Submission", "approval": "Approval",
    "disbursement": "Disbursement", "crosscut": "Data & Platform",
}

# Order matters: write intents first (specific verbs), then standup, then the
# manager keywords, then the LM oversight view. "assign " has a trailing space
# so it does not swallow "what's assigned to me" (briefing).
ROUTES = [
    # flag first: a "flag … and assign … to investigate" request is a flag action,
    # and must win over the 'assign' keyword it also contains.
    ({"flag", "investigate", "open investigation", "open an investigation",
      "raise an investigation", "look into the drop"}, "flag"),
    ({"create ", "create a", "add ticket", "add a ticket", "new ticket",
      "new initiative", "open a ticket", "file a ticket", "log a ticket",
      "tao ticket", "tạo ticket", "tao moi", "them ticket"}, "create"),
    ({"assign ", "re-assign", "reassign ", "giao cho", "gan cho", "gán cho"}, "assign"),
    ({"standup", "stand-up", "stand up", "daily"}, "standup"),
    ({"decide", "decision", "decided", "document", "wiki", "confluence", "wrote",
      "quyết định", "quyet dinh", "tài liệu", "tai lieu", "biên bản", "bien ban"}, "knowledge"),
    ({"plate", "my task", "my issue", "my initiative", "assigned to me", "what should i",
      "việc của tôi", "viec cua toi"}, "briefing"),
    ({"metric", "conversion", "submission rate", "approval rate", "disbursement rate",
      "traffic", "ticket size", "funnel performance", "funnel numbers", "funnel table",
      "performance", "e2e", "throughput", "how is the funnel doing", "ty le", "chuyen doi",
      "compare", "what changed", "concerning", "drop", "dropped", "month over month",
      "mom", "vs last month", "anomal"},
     "metrics"),
    ({"oversight", "overview", "funnel", "digest", "who is working", "who's working",
      "who owns", "ownership", "on track", "off track", "off-track", "critical",
      "at risk", "behind", "slipping", "manager", "lead", "report", "status of",
      "ai đang làm", "ai dang lam", "tổng quan", "tong quan", "quan trọng", "quan trong",
      "trễ", "tre ", "rủi ro", "rui ro"}, "oversight"),
    ({"sprint", "team", "pulse", "progress", "stuck", "blocked", "workload", "overdue",
      "tiến độ", "tien do", "nhóm", "nhom"}, "sprint"),
]

VALID = {"create", "assign", "flag", "metrics", "oversight", "briefing", "sprint", "knowledge", "standup", "help"}


def route(message: str) -> str:
    msg = message.lower()
    for keywords, intent in ROUTES:
        if any(k in msg for k in keywords):
            return intent
    return rp_classify(message) or "help"


def rp_classify(message: str) -> str | None:
    out = rp.llm_chat(
        "Classify the user's message about a lending-funnel initiative tracker into exactly "
        "one word from: create, assign, oversight, briefing, sprint, knowledge, standup, help. "
        "create = make a NEW initiative/ticket; assign = set the owner of an EXISTING ticket; "
        "flag = a significant month-over-month metric DROP should be flagged and an investigation "
        "opened for the stage owner; "
        "metrics = funnel PERFORMANCE numbers/conversion rates per month (traffic, submission, "
        "approval, disbursement, ticket size), including comparing months; "
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


# --------------------------------------------------------------- write helpers
import re  # noqa: E402

_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
_CREATE_PREFIX = re.compile(
    r"^\s*(please\s+)?(create|add|open|file|log|make|new)\b[^:]*?(ticket|initiative|task|issue)?\s*[:\-]?\s*",
    re.IGNORECASE)


def extract_create_fields(message: str) -> dict | None:
    """LLM extracts a structured initiative; falls back to a heuristic if the LLM
    is offline so creation still works."""
    raw = rp.llm_chat(
        "Extract a Jira initiative from the user's message as STRICT JSON with keys: "
        "summary (short imperative string), "
        "stage (one of traffic, submission, approval, disbursement, crosscut, or null), "
        "owner (a person's name, or null), due (YYYY-MM-DD or null). "
        "Infer stage from the topic when obvious "
        "(eligible traffic/acquisition->traffic, application submit/document upload->submission, "
        "approval/underwriting->approval, payout/e-sign->disbursement). Reply with ONLY the JSON object.",
        message, max_tokens=300)
    fields = None
    if raw:
        try:
            s = raw.strip().strip("`")
            s = s[s.find("{"): s.rfind("}") + 1]
            fields = json.loads(s)
        except Exception:  # noqa: BLE001
            fields = None
    if not fields or not fields.get("summary"):
        summary = _CREATE_PREFIX.sub("", message).strip().rstrip("?.!") or message.strip()
        fields = {"summary": summary, "stage": None, "owner": None, "due": None}
    return fields


def parse_assign(message: str):
    """Pull an issue key and target owner from e.g. 'assign KAN-23 to Mai'."""
    m = _KEY_RE.search(message)
    key = m.group(1) if m else None
    owner = None
    mt = re.search(r"\bto\s+([A-Za-z][\w '.-]*)$", message.strip())
    if mt:
        owner = mt.group(1).strip().rstrip(" ?.!")
    return key, owner


# ---------------------------------------------------------------- entrypoint

NARRATE_SYS = {
    "oversight": "You are briefing the lending lead on the funnel initiatives. Lead with "
                 "'needs_attention_now' (anything overdue or blocked) — name the item, owner and "
                 "why — then mention what's 'due_soon'. Give a short read on each Epic (funnel "
                 "stage / project) from 'by_epic' and flag any owner carrying off-track work. Quote "
                 "issue keys and owners. Be decisive and brief; for a breakdown use a markdown table.",
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

    if intent in ("create", "assign"):
        return _handle_write(intent, message)
    if intent == "flag":
        return _handle_flag(message)

    answer = None
    if intent == "metrics":
        result = fm.summary()
        lang_hint = "Reply in Vietnamese." if lang == "vi" else "Reply in English."
        headline = rp.llm_chat(
            "You are Funnel Watchtower. In ONE or TWO sentences give the lead the headline trend "
            "from this funnel data: name the latest month, its end-to-end rate, and the single most "
            "notable month-over-month change. Use ONLY these numbers, never invent. " + lang_hint,
            json.dumps(result, ensure_ascii=False), max_tokens=200)
        heads_up = ""
        if result.get("anomalies"):
            owners = bf.stage_owners()
            al = []
            for a in result["anomalies"]:
                o = owners.get(a["stage"])
                al.append(f"**{a['metric']}** fell {abs(a['delta_pp'])}pp "
                          f"({a['prev_pct']}%→{a['latest_pct']}%) {a['prev_month']}→{a['latest_month']}"
                          + (f", owned by {o}" if o else ""))
            heads_up = ("> ⚠ **Needs attention:** " + "; ".join(al) +
                        ". Say \"flag it\" and I'll open an investigation for the owner.\n\n")
        answer = heads_up + (headline + "\n\n" if headline else "") + fm.render_markdown()
    elif intent == "oversight":
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
        result = {"hint": "Try: show me the funnel metrics · give me the funnel overview · "
                          "who is working on what? · what's critical or off track? · "
                          "create a ticket to ... · assign KAN-12 to <name> · "
                          "what did we decide about submission? · draft my standup"}
        answer = (
            "Hi! I'm Funnel Watchtower (Team UW). I track the loan funnel (Traffic → Submission → "
            "Approval → Disbursement) across Jira + Confluence. Ask me for the **funnel metrics**, "
            "the **funnel overview** (who owns what, what's critical or off track), to **create** "
            "or **assign** an initiative, a past **decision**, or your **plate**. "
            "Tiếng Việt cũng được nhé!"
        )

    # LLM narration with intent-specific instructions (deterministic JSON is the truth)
    if answer is None:
        sys_extra = NARRATE_SYS.get(intent, "")
        lang_line = "Answer in Vietnamese." if lang == "vi" else "Answer in the user's language (default English)."
        out = rp.llm_chat(
            "You are Funnel Watchtower, a lending-funnel initiative tracker for the team lead. "
            "Use ONLY the JSON data provided — never invent issues, owners or numbers. "
            "FIRST, answer the user's actual question directly. If it's a narrow or factual "
            "question (a count, one owner, a single item, yes/no), reply in 1–2 sentences with "
            "just that answer and stop — do NOT dump the full report. Only if the user asked for a "
            "broad overview/status/digest should you give the fuller breakdown. When you do: " +
            sys_extra + " If the user asks for a table, use a markdown table. " + lang_line,
            "Question: " + message + "\nData JSON:\n" + json.dumps(result, ensure_ascii=False),
            max_tokens=900,
        )
        answer = out or json.dumps(result, ensure_ascii=False, indent=2)

    return _respond(intent, answer, result)


def _handle_flag(message: str) -> dict:
    """Detect significant MoM rate drops and open an investigation Task for the
    owner of the affected stage (under that stage's Epic)."""
    drops = fm.anomalies()
    if not drops:
        return _respond("flag", "No significant month-over-month drops right now — "
                                "the funnel looks stable.", {"anomalies": []})
    owners = bf.stage_owners()
    lines, created = [], []
    for a in drops:
        owner = owners.get(a["stage"])
        line = (f"{a['metric']} fell {abs(a['delta_pp'])}pp "
                f"({a['prev_pct']}%→{a['latest_pct']}%, {a['delta_pct']}%) "
                f"from {a['prev_month']} to {a['latest_month']}")
        if owner:
            line += f" — owner: {owner}"
        if ALLOW_WRITES:
            assignee_id = None
            if owner:
                u = jc.find_assignable_user(owner)
                if u:
                    assignee_id = u["accountId"]
            epic_name = STAGE_TO_EPIC.get(a["stage"])
            epic_key = jc.find_epic(epic_name) if epic_name else None
            title = (f"Investigate: {a['metric']} dropped {abs(a['delta_pp'])}pp in "
                     f"{a['latest_month']} ({a['prev_pct']}%→{a['latest_pct']}%)")
            res = jc.create_issue(summary=title, stage=a["stage"], owner=None, due=None,
                                  assignee_id=assignee_id, epic_key=epic_key)
            if res.get("key"):
                created.append(res["key"])
                line += f" → opened {res['key']}" + (f" for {owner}" if owner else "")
            elif res.get("error"):
                line += " (couldn't open task)"
        lines.append("- " + line)
    verb = "Flagged and opened investigation task(s)" if created else "Flagged"
    answer = f"{verb} for {len(drops)} significant drop(s):\n\n" + "\n".join(lines)
    if not ALLOW_WRITES:
        answer += "\n\n_(Writes are off, so I only flagged them.)_"
    return _respond("flag", answer, {"anomalies": drops, "created": created})


def _handle_write(intent: str, message: str) -> dict:
    if not ALLOW_WRITES:
        return _respond(intent, "Writing to Jira is disabled on this deployment "
                                "(set ALLOW_WRITES=true to enable).", {"allow_writes": False})

    if intent == "create":
        f = extract_create_fields(message)
        owner = f.get("owner")
        assignee_id = None
        assign_note = ""
        if owner:
            u = jc.find_assignable_user(owner)
            if u:
                assignee_id = u["accountId"]
                assign_note = f"assigned to {u['displayName']}"
            else:
                assign_note = (f"tagged owner-{owner.strip().lower().replace(' ', '-')} "
                               f"(no Jira user matched '{owner}', so not assigned to a real account)")
        else:
            # no owner given -> assign to yourself (the caller / token user)
            me = jc.myself()
            if me:
                assignee_id = me["accountId"]
                assign_note = f"assigned to you ({me['displayName']})"
        # the Epic (funnel stage / project) the task belongs under
        stage = (f.get("stage") or "").lower() or None
        epic_name = STAGE_TO_EPIC.get(stage) if stage else None
        epic_key = jc.find_epic(epic_name) if epic_name else None
        res = jc.create_issue(summary=f["summary"], stage=stage, owner=owner,
                              due=f.get("due"), assignee_id=assignee_id, epic_key=epic_key)
        if res.get("error"):
            return _respond("create", f"Couldn't create that initiative ({res['error']}).", res)
        notified = _notify_teams("New task created", res.get("key"))
        bits = []
        if epic_name:
            bits.append(f"Epic: {epic_name}" + ("" if res.get("epic_key") else " (label only)"))
        if f.get("due"):
            bits.append(f"due {f['due']}")
        else:
            bits.append("backlog (no due date)")
        if assign_note:
            bits.append(assign_note)
        answer = f"Created **{res['key']}** — {f['summary']}"
        if bits:
            answer += " (" + ", ".join(bits) + ")"
        answer += f". {res['url']}"
        if notified:
            answer += " · 📨 sent to Teams"
        return _respond("create", answer, {**res, "fields": f})

    # intent == "assign"
    key, owner = parse_assign(message)
    if not key or not owner:
        return _respond("assign", "Tell me which ticket and who — e.g. "
                                  "\"assign KAN-23 to Mai\".", {"parsed": {"key": key, "owner": owner}})
    u = jc.find_assignable_user(owner)
    res = jc.assign_issue(key, assignee_id=(u["accountId"] if u else None), owner=owner)
    if u and res.get("assigned_real"):
        answer = f"Assigned **{key}** to {u['displayName']} (owner-{owner.strip().lower()} stamped too)."
    elif res.get("owner_label"):
        answer = (f"Set **{key}** owner to {owner} (label {res['owner_label']}). No matching Jira "
                  f"user to assign for real — invite {owner} to the workspace to enable real assignment.")
    else:
        answer = f"Couldn't assign {key} ({res.get('error', 'unknown error')})."
    return _respond("assign", answer, res)


def _notify_teams(header: str, key: str | None) -> bool:
    """Post the full Jira issue as an Adaptive Card to Teams. Best-effort:
    a Teams/webhook failure must never break the Jira action."""
    if not key or not tc.configured():
        return False
    try:
        full = jc.get_issue_full(key)
        return tc.issue_card(full, header=f"{header} — {key}")
    except Exception:  # noqa: BLE001
        return False


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
