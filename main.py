"""Lending Portfolio Watchdog — v0 (no LLM).

Minimal AgentBase agent that answers portfolio questions from the synthetic
loan CSV using keyword routing. Purpose: validate the deploy pipeline
end-to-end with zero MaaS token consumption. v1 will add Qwen 3 for
natural-language understanding and phrasing.

Team UW — Claw-a-thon 2026. Data is 100% synthetic (see data/).
"""

import csv
import os
from collections import defaultdict
from datetime import datetime

from greennode_agentbase import (
    GreenNodeAgentBaseApp,
    PingStatus,
    RequestContext,
)

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


# ------------------------------------------------------------- intent router
# v0: dumb keyword matching. v1 replaces this with Qwen 3.

ROUTES = [
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
    return "help"


# ---------------------------------------------------------------- entrypoint


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    message = str(payload.get("message", ""))
    intent = route(message)

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
        }
    else:
        result = {
            "hint": "Try asking about: portfolio summary, flagged/at-risk accounts, "
                    "breakdown by province, or breakdown by segment/product.",
        }

    return {
        "status": "success",
        "intent": intent,
        "result": result,
        "disclaimer": "Synthetic data only — Claw-a-thon 2026 demo.",
        "timestamp": datetime.now().isoformat(),
    }


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
