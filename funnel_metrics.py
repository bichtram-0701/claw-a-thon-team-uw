"""Funnel performance metrics — Funnel Watchtower, Team UW.

Loads the synthetic monthly funnel data and computes the conversion rates between
stages (Traffic -> Submission -> Approval -> Disbursement), average ticket size,
and month-over-month deltas. Deterministic: the LLM narrates trends, but every
number here is computed, never invented. Renders a chat-ready markdown table.
"""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "data", "funnel_metrics.json")
STAGE_ORDER = ["traffic", "submission", "approval", "disbursement"]


def _load() -> dict:
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def _pct(num: float, den: float) -> float | None:
    return round(100 * num / den, 1) if den else None


def rows() -> list[dict]:
    """Per-month volumes + derived rates + avg ticket size."""
    out = []
    for m in _load()["months"]:
        t, s, a, d = m["traffic"], m["submission"], m["approval"], m["disbursement"]
        amt = m.get("disbursement_amount_vnd", 0)
        out.append({
            "month": m["month"],
            "traffic": t, "submission": s, "approval": a, "disbursement": d,
            "disbursement_amount_vnd": amt,
            "avg_ticket_vnd": round(amt / d) if d else 0,
            "submission_rate_pct": _pct(s, t),
            "approval_rate_pct": _pct(a, s),
            "disbursement_rate_pct": _pct(d, a),
            "e2e_rate_pct": _pct(d, t),
        })
    return out


def summary() -> dict:
    """Structured snapshot for the LLM: latest month, MoM deltas, and the data."""
    r = rows()
    latest, prev = (r[-1], r[-2]) if len(r) >= 2 else (r[-1], None)

    def delta(key):
        if not prev or latest.get(key) is None or prev.get(key) is None:
            return None
        return round(latest[key] - prev[key], 1)

    return {
        "partner": _load().get("partner"),
        "stages": STAGE_ORDER,
        "stage_definitions": _load().get("stage_definitions", {}),
        "latest_month": latest["month"],
        "latest": latest,
        "mom_pp": {  # percentage-point change vs previous month
            "submission_rate": delta("submission_rate_pct"),
            "approval_rate": delta("approval_rate_pct"),
            "disbursement_rate": delta("disbursement_rate_pct"),
            "e2e_rate": delta("e2e_rate_pct"),
        },
        "months": r,
        "note": "Rates are computed from counts; do not invent figures. "
                "submission=submission/traffic, approval=approval/submission, "
                "disbursement=disbursement/approval, e2e=disbursement/traffic.",
    }


def _b(v):
    return f"{v / 1e9:.1f}B"


def _m(v):
    return f"{v / 1e6:.1f}M"


def render_markdown() -> str:
    """Two tables (volumes, then rates) with months as columns — like the LM deck."""
    r = rows()
    months = [x["month"] for x in r]
    head = "| Metric | " + " | ".join(months) + " |"
    sep = "|" + "---|" * (len(months) + 1)

    def line(label, vals):
        return "| " + label + " | " + " | ".join(vals) + " |"

    vol = [head, sep,
           line("Traffic", [f"{x['traffic']:,}" for x in r]),
           line("Submission", [f"{x['submission']:,}" for x in r]),
           line("Approval", [f"{x['approval']:,}" for x in r]),
           line("Disbursement", [f"{x['disbursement']:,}" for x in r]),
           line("Disb. amount (VND)", [_b(x["disbursement_amount_vnd"]) for x in r]),
           line("Avg ticket (VND)", [_m(x["avg_ticket_vnd"]) for x in r])]

    rate = [head.replace("Metric", "Rate"), sep,
            line("Submission (Sub/Traffic)", [f"{x['submission_rate_pct']}%" for x in r]),
            line("Approval (Appr/Sub)", [f"{x['approval_rate_pct']}%" for x in r]),
            line("Disbursement (Disb/Appr)", [f"{x['disbursement_rate_pct']}%" for x in r]),
            line("Traffic E2E (Disb/Traffic)", [f"{x['e2e_rate_pct']}%" for x in r])]

    return ("**Funnel — monthly volumes**\n\n" + "\n".join(vol) +
            "\n\n**Conversion rates**\n\n" + "\n".join(rate))
