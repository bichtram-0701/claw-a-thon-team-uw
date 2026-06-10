"""Lending Portfolio Watchdog — v1 (Qwen 3 via GreenNode MaaS).

Architecture: analysis runs in plain Python over the synthetic CSV (cheap,
deterministic); Qwen 3 understands the question and phrases the answer
from those precomputed numbers. If the LLM is unreachable or unconfigured,
the agent degrades gracefully to v0 keyword routing with raw JSON answers.

Team UW — Claw-a-thon 2026. Data is 100% synthetic (see data/).
"""

import csv
import json
import os
from collections import defaultdict
from datetime import datetime

import httpx
from greennode_agentbase import (
    GreenNodeAgentBaseApp,
    PingStatus,
    RequestContext,
)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "loan_portfolio_synthetic.csv")
NPL_DPD_THRESHOLD = 91          # days past due at which a loan becomes NPL
WATCH_WINDOW = 6                # flag loans within this many days of the threshold

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "")  # empty = auto-discover a Qwen model
LLM_TIMEOUT = 30.0
MAX_ANSWER_TOKENS = 500

app = GreenNodeAgentBaseApp()

# ---------------------------------------------------------------- data layer
# (the "adapter": v-next swaps this loader for a real data source)


def load_portfolio() -> list[dict]:
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["days_past_due"] = int(r["days_past_due"])
        r["outstanding_vnd"] = int(r["outstanding_vnd"])
        r["principal_vnd"] = int(r["principal_vnd"])
    return rows


PORTFOLIO = load_portfolio()

# ------------------------------------------------------------ analysis tools


def bad_rate(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    bad = sum(1 for r in rows if r["status"] in ("overdue", "npl"))
    return round(100 * bad / len(rows), 1)


def portfolio_summary() -> dict:
    by_status = defaultdict(int)
    for r in PORTFOLIO:
        by_status[r["status"]] += 1
    return {
        "loans_total": len(PORTFOLIO),
        "outstanding_vnd": sum(r["outstanding_vnd"] for r in PORTFOLIO),
        "by_status": dict(by_status),
        "bad_rate_pct": bad_rate(PORTFOLIO),
    }


def flagged_accounts() -> dict:
    lo = NPL_DPD_THRESHOLD - WATCH_WINDOW
    flagged = [
        {
            "loan_id": r["loan_id"],
            "product_type": r["product_type"],
            "province": r["province"],
            "days_past_due": r["days_past_due"],
            "outstanding_vnd": r["outstanding_vnd"],
            "days_until_npl": NPL_DPD_THRESHOLD - r["days_past_due"],
        }
        for r in PORTFOLIO
        if lo <= r["days_past_due"] < NPL_DPD_THRESHOLD
    ]
    flagged.sort(key=lambda x: x["days_until_npl"])
    return {"flagged_count": len(flagged), "accounts": flagged}


def breakdown(field: str) -> dict:
    groups = defaultdict(list)
    for r in PORTFOLIO:
        groups[r[field]].append(r)
    return {
        k: {"loans": len(v), "bad_rate_pct": bad_rate(v)}
        for k, v in sorted(groups.items(), key=lambda kv: -bad_rate(kv[1]))
    }


def vintage_analysis() -> dict:
    """Recent (<=180 days on book) vs older loans, by product."""
    today = datetime.now().date()
    out = {}
    for product in sorted({r["product_type"] for r in PORTFOLIO}):
        rows = [r for r in PORTFOLIO if r["product_type"] == product]
        recent, older = [], []
        for r in rows:
            orig = datetime.fromisoformat(r["origination_date"]).date()
            (recent if (today - orig).days <= 180 else older).append(r)
        out[product] = {
            "recent_vintage": {"loans": len(recent), "bad_rate_pct": bad_rate(recent)},
            "older_vintage": {"loans": len(older), "bad_rate_pct": bad_rate(older)},
        }
    return out


def full_picture() -> dict:
    """Everything Qwen needs to answer any portfolio question. ~2 KB."""
    return {
        "summary": portfolio_summary(),
        "flagged_near_npl": flagged_accounts(),
        "by_province": breakdown("province"),
        "by_product": breakdown("product_type"),
        "by_customer_segment": breakdown("segment"),
        "vintage_recent_vs_older": vintage_analysis(),
        "definitions": {
            "bad_rate_pct": "share of loans overdue or NPL",
            "npl": "loan with days_past_due >= " + str(NPL_DPD_THRESHOLD),
            "flagged": "loans within " + str(WATCH_WINDOW) + " days of becoming NPL",
        },
    }


# ------------------------------------------------------------------ LLM brain

_model_cache = {"name": LLM_MODEL}

SYSTEM_PROMPT = (
    "You are Lending Portfolio Watchdog, a risk analysis assistant built by "
    "Team UW for a loan portfolio team. You receive precomputed portfolio "
    "statistics as JSON and must answer the user's question using ONLY those "
    "numbers - never invent figures. Be concise and businesslike. Lead with "
    "the direct answer, quote concrete numbers, and add one short insight if "
    "the data shows something notable (e.g. a deteriorating segment). Amounts "
    "are in VND. Answer in the same language as the question (Vietnamese or "
    "English). If the question is unrelated to the portfolio, say what you "
    "can help with instead. All data is synthetic demo data for Claw-a-thon 2026."
)


def resolve_model(client) -> str:
    """Pick a Qwen model from the OpenAI-compatible /models list (cached)."""
    if _model_cache["name"]:
        return _model_cache["name"]
    resp = client.get(LLM_BASE_URL + "/models")
    resp.raise_for_status()
    ids = [m.get("id", "") for m in resp.json().get("data", [])]
    qwen = [i for i in ids if "qwen" in i.lower()]
    _model_cache["name"] = qwen[0] if qwen else (ids[0] if ids else "")
    return _model_cache["name"]


def ask_llm(question: str) -> str:
    headers = {"Authorization": "Bearer " + LLM_API_KEY}
    with httpx.Client(timeout=LLM_TIMEOUT, headers=headers) as client:
        model = resolve_model(client)
        if not model:
            raise RuntimeError("no model available")
        body = {
            "model": model,
            "max_tokens": MAX_ANSWER_TOKENS,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "Portfolio statistics (JSON):\n"
                    + json.dumps(full_picture(), ensure_ascii=False)
                    + "\n\nQuestion: " + question,
                },
            ],
        }
        resp = client.post(LLM_BASE_URL + "/chat/completions", json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


# ----------------------------------------------------- v0 fallback (no LLM)

ROUTES = [
    ({"flag", "watch", "alert", "risk", "npl", "canh bao", "cảnh báo", "rui ro", "rủi ro"}, "flagged"),
    ({"province", "region", "tinh", "tỉnh", "khu vuc", "khu vực"}, "province"),
    ({"segment", "phan khuc", "phân khúc", "product", "san pham", "sản phẩm"}, "segment"),
    ({"summary", "overview", "health", "tong quan", "tổng quan", "danh muc", "danh mục"}, "summary"),
]


def keyword_fallback(message: str) -> dict:
    msg = message.lower()
    for keywords, intent in ROUTES:
        if any(k in msg for k in keywords):
            break
    else:
        intent = "help"
    data = {
        "summary": portfolio_summary,
        "flagged": flagged_accounts,
        "province": lambda: breakdown("province"),
        "segment": lambda: {"by_product": breakdown("product_type"), "by_segment": breakdown("segment")},
        "help": lambda: {"hint": "Ask about: portfolio summary, at-risk accounts, provinces, segments."},
    }[intent]()
    return {"intent": intent, "data": data}


# ---------------------------------------------------------------- entrypoint


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    message = str(payload.get("message", "")).strip() or "portfolio summary"

    answer, llm_used, fallback = None, False, None
    if LLM_API_KEY:
        try:
            answer = ask_llm(message)
            llm_used = True
        except Exception as e:  # any LLM failure degrades gracefully
            fallback = "LLM unavailable (" + type(e).__name__ + "); using keyword mode"
    if not llm_used:
        kw = keyword_fallback(message)
        answer = json.dumps(kw["data"], ensure_ascii=False, indent=2)
        if not fallback:
            fallback = "LLM not configured; using keyword mode"

    result = {
        "status": "success",
        "answer": answer,
        "llm_used": llm_used,
        "disclaimer": "Synthetic data only — Claw-a-thon 2026 demo.",
        "timestamp": datetime.now().isoformat(),
    }
    if fallback:
        result["note"] = fallback
    return result


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
