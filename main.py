"""Lending Portfolio Watchdog — v1 (Q&A + watchdog + LLM report).

v0 (Rino): synthetic portfolio, keyword Q&A routing, watchdog flags.
v1 adds:  - "report" intent: full manager-ready portfolio report (metrics.py + report.py)
          - LLM (MaaS Qwen/Gemma): intent classification when keywords miss,
            natural-language answers, narrative reports
          - vintage analysis: recent vs older originations by product
          - graceful fallback: every LLM feature degrades to deterministic
            output, so the agent works even with zero MaaS availability.

Team UW — Claw-a-thon 2026. Data is 100% synthetic (see data/).
"""

import csv
import os
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv
from greennode_agentbase import (
    GreenNodeAgentBaseApp,
    PingStatus,
    RequestContext,
)

import metrics as mx
import report as rp

load_dotenv()

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "loan_portfolio_synthetic.csv")
NPL_DPD_THRESHOLD = 91          # days past due at which a loan becomes NPL
WATCH_WINDOW = 6                # flag loans within this many days of the threshold

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
    """Share of loans overdue or NPL, in %."""
    if not rows:
        return 0.0
    bad = sum(1 for r in rows if r["status"] in ("overdue", "npl"))
    return round(100 * bad / len(rows), 1)


def portfolio_summary() -> dict:
    total_outstanding = sum(r["outstanding_vnd"] for r in PORTFOLIO)
    by_status = defaultdict(int)
    for r in PORTFOLIO:
        by_status[r["status"]] += 1
    return {
        "loans_total": len(PORTFOLIO),
        "outstanding_vnd": total_outstanding,
        "by_status": dict(by_status),
        "bad_rate_pct": bad_rate(PORTFOLIO),
    }


def flagged_accounts() -> dict:
    """Loans within WATCH_WINDOW days of rolling into NPL."""
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


def full_report(payload: dict) -> dict:
    """Manager-ready portfolio report (markdown). Optional prior-period CSV
    in payload["prev_csv_text"] enables trend analysis."""
    lang = payload.get("language", "vi")
    cur = mx.analyze(mx.from_rows(PORTFOLIO))
    delta = None
    if payload.get("prev_csv_text"):
        delta = mx.compare(cur, mx.analyze(mx.load_csv(payload["prev_csv_text"])))
    md, mode = rp.portfolio_report(cur, delta, lang)
    return {"report_markdown": md, "report_mode": mode, "metrics": cur, "delta": delta}


# ------------------------------------------------------------- intent router
# Keyword matching first (free); LLM classification when keywords miss.

ROUTES = [
    ({"report", "bao cao", "báo cáo", "weekly", "tuan", "tuần"}, "report"),
    ({"flag", "watch", "alert", "risk", "npl", "canh bao", "cảnh báo", "rui ro", "rủi ro"}, "flagged"),
    ({"province", "region", "tinh", "tỉnh", "khu vuc", "khu vực"}, "province"),
    ({"segment", "phan khuc", "phân khúc", "product", "san pham", "sản phẩm"}, "segment"),
    ({"summary", "overview", "health", "tong quan", "tổng quan", "danh muc", "danh mục"}, "summary"),
]


def route(message: str) -> str:
    msg = message.lower()
    for keywords, intent in ROUTES:
        if any(k in msg for k in keywords):
            return intent
    return rp.classify_intent(message) or "help"


# ---------------------------------------------------------------- entrypoint


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    message = str(payload.get("message", ""))
    lang = payload.get("language", "vi")
    intent = route(message)

    answer = None
    if intent == "summary":
        result = portfolio_summary()
    elif intent == "flagged":
        result = flagged_accounts()
    elif intent == "province":
        result = breakdown("province")
    elif intent == "segment":
        result = {
            "by_product": breakdown("product_type"),
            "by_segment": breakdown("segment"),
            "vintage_recent_vs_older": vintage_analysis(),
        }
    elif intent == "report":
        result = full_report(payload)
        answer = result["report_markdown"]
    else:
        result = {
            "hint": "Try asking about: portfolio summary, flagged/at-risk accounts, "
                    "breakdown by province, segment/product, or a full report.",
        }

    # Natural-language phrasing for Q&A intents (LLM; skipped when offline)
    if answer is None and intent in ("summary", "flagged", "province", "segment") and message:
        answer = rp.narrate(message, result, lang)

    return {
        "status": "success",
        "intent": intent,
        "answer": answer,
        "result": result,
        "disclaimer": "Synthetic data only — Claw-a-thon 2026 demo.",
        "timestamp": datetime.now().isoformat(),
    }


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
