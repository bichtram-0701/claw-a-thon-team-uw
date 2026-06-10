"""Application funnel analytics — Lending Portfolio Watchdog, Team UW.

Funnel: applied -> docs_submitted -> approved -> disbursed.
Synthetic data only (data/funnel_synthetic.csv).
"""
import csv
import os
from collections import defaultdict
from datetime import date, timedelta

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "funnel_synthetic.csv")
STAGES = ["applied", "docs_submitted", "approved", "disbursed"]
_IDX = {s: i for i, s in enumerate(STAGES)}
RECENT_DAYS = 28


def load_funnel() -> list[dict]:
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["requested_vnd"] = int(r["requested_vnd"])
    return rows


FUNNEL = load_funnel()


def _reached(rows, stage):
    return [r for r in rows if _IDX[r["final_stage"]] >= _IDX[stage]]


def _rate(rows, frm, to):
    a, b = len(_reached(rows, frm)), len(_reached(rows, to))
    return round(100 * b / a, 1) if a else 0.0


def stage_conversion(rows=None) -> dict:
    rows = rows if rows is not None else FUNNEL
    out = {"applications": len(rows)}
    for frm, to in zip(STAGES, STAGES[1:]):
        out[f"{frm}->{to}_pct"] = _rate(rows, frm, to)
    out["end_to_end_pct"] = _rate(rows, "applied", "disbursed")
    return out


def by_dimension(field: str) -> dict:
    groups = defaultdict(list)
    for r in FUNNEL:
        groups[r[field]].append(r)
    return {k: stage_conversion(v) for k, v in sorted(groups.items())}


def drop_reasons() -> dict:
    reasons = defaultdict(int)
    for r in FUNNEL:
        if r["drop_reason"]:
            reasons[r["drop_reason"]] += 1
    total = sum(reasons.values())
    return {k: {"count": v, "pct_of_drops": round(100 * v / total, 1)}
            for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])}


def recent_vs_older() -> dict:
    """Approval-rate shift, recent vs older applications, by product."""
    cutoff = date(2026, 6, 10) - timedelta(days=RECENT_DAYS)
    out = {}
    for product in sorted({r["product_type"] for r in FUNNEL}):
        rows = [r for r in FUNNEL if r["product_type"] == product]
        recent = [r for r in rows if date.fromisoformat(r["applied_date"]) > cutoff]
        older = [r for r in rows if date.fromisoformat(r["applied_date"]) <= cutoff]
        out[product] = {
            "recent_approval_pct": _rate(recent, "docs_submitted", "approved"),
            "older_approval_pct": _rate(older, "docs_submitted", "approved"),
            "recent_apps": len(recent), "older_apps": len(older),
        }
    return out


def funnel_picture() -> dict:
    """Everything the LLM needs to answer funnel questions."""
    return {
        "overall": stage_conversion(),
        "by_product": by_dimension("product_type"),
        "by_channel": by_dimension("channel"),
        "drop_reasons": drop_reasons(),
        "approval_shift_recent_vs_older": recent_vs_older(),
        "definitions": {
            "funnel_stages": " -> ".join(STAGES),
            "end_to_end_pct": "share of applications that reach disbursement",
            "recent": f"applications in the last {RECENT_DAYS} days",
        },
    }
