"""Funnel performance metrics — Funnel Agent, Team UW.

Loads the synthetic row-level funnel fixture and computes monthly conversion rates
between stages (Traffic -> Submission -> Approval -> Disbursement), average
ticket size, and month-over-month deltas. Deterministic: the LLM narrates
trends, but every number here is computed, never invented.

`data/funnel_synthetic.csv` is the runtime source of truth for volumes. The JSON
file stores targets, stage definitions, and the seed monthly totals used by the
deterministic data generator.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from functools import lru_cache

_PATH = os.path.join(os.path.dirname(__file__), "data", "funnel_metrics.json")
_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "funnel_synthetic.csv")
STAGE_ORDER = ["traffic", "submission", "approval", "completion"]
_STAGE_RANK = {
    # Current generic stage values.
    "traffic": 1,
    "submitted": 2,
    "approved": 3,
    "completed": 4,
    # Backward-compatible aliases for older fixture revisions.
    "applied": 1,
    "docs_submitted": 2,
}


def _load() -> dict:
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def _pct(num: float, den: float) -> float | None:
    return round(100 * num / den, 1) if den else None


def _row_from_counts(month: str, t: int, s: int, a: int, d: int, amt: int) -> dict:
    return {
        "month": month,
        "traffic": t,
        "submission": s,
        "approval": a,
        "completion": d,
        "completion_amount_vnd": amt,
        "avg_ticket_vnd": round(amt / d) if d else 0,
        "submission_rate_pct": _pct(s, t),
        "approval_rate_pct": _pct(a, s),
        "completion_rate_pct": _pct(d, a),
        "e2e_rate_pct": _pct(d, t),
    }


def _rows_from_json() -> list[dict]:
    out = []
    for m in _load()["months"]:
        out.append(_row_from_counts(
            m["month"],
            int(m["traffic"]),
            int(m["submission"]),
            int(m["approval"]),
            int(m["completion"]),
            int(m.get("completion_amount_vnd", 0)),
        ))
    return out


def _rows_from_csv() -> list[dict]:
    monthly = defaultdict(lambda: {
        "traffic": 0,
        "submission": 0,
        "approval": 0,
        "completion": 0,
        "completion_amount_vnd": 0,
    })
    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            month = (row.get("entered_date") or row.get("applied_date") or "")[:7]
            rank = _STAGE_RANK.get(row.get("final_stage", ""), 0)
            monthly[month]["traffic"] += 1
            monthly[month]["submission"] += int(rank >= 2)
            monthly[month]["approval"] += int(rank >= 3)
            monthly[month]["completion"] += int(rank == 4)
            if rank == 4:
                monthly[month]["completion_amount_vnd"] += int(row.get("potential_value_vnd") or row.get("requested_vnd") or 0)
    out = []
    for month in sorted(monthly):
        m = monthly[month]
        out.append(_row_from_counts(
            month,
            m["traffic"],
            m["submission"],
            m["approval"],
            m["completion"],
            m["completion_amount_vnd"],
        ))
    return out


@lru_cache(maxsize=1)
def _cached_rows() -> tuple[tuple[tuple[str, object], ...], ...]:
    if os.path.exists(_CSV_PATH):
        try:
            data = _rows_from_csv()
        except Exception:  # noqa: BLE001 - keep the demo robust if CSV is missing/corrupt
            data = _rows_from_json()
    else:
        data = _rows_from_json()
    # Cache immutable key/value tuples so callers cannot mutate shared state.
    return tuple(tuple(row.items()) for row in data)


def rows() -> list[dict]:
    """Per-month volumes + derived rates + average ticket size.

    Prefer the row-level CSV so daily, weekly, and monthly views reconcile. Fall
    back to the JSON fixture if the CSV is not packaged.
    """
    return [dict(items) for items in _cached_rows()]


def summary() -> dict:
    """Structured snapshot for the LLM: latest month, MoM deltas, and the data."""
    r = rows()
    latest, prev = (r[-1], r[-2]) if len(r) >= 2 else (r[-1], None)

    def delta(key):
        if not prev or latest.get(key) is None or prev.get(key) is None:
            return None
        return round(latest[key] - prev[key], 1)

    meta = _load()
    return {
        "partner": meta.get("partner"),
        "stages": STAGE_ORDER,
        "stage_definitions": meta.get("stage_definitions", {}),
        "latest_month": latest["month"],
        "latest": latest,
        "mom_pp": {  # percentage-point change vs previous month
            "submission_rate": delta("submission_rate_pct"),
            "approval_rate": delta("approval_rate_pct"),
            "completion_rate": delta("completion_rate_pct"),
            "e2e_rate": delta("e2e_rate_pct"),
        },
        "months": r,
        "targets": targets(),
        "target_misses": target_misses(),   # latest-month rates below OKR target
        "anomalies": anomalies(),   # significant MoM rate drops to flag
        "note": "Rates are computed from row-level CSV counts when available; do not invent figures. "
                "submission=submission/traffic, approval=approval/submission, "
                "disbursement=disbursement/approval, e2e=disbursement/traffic.",
    }


# A drop counts as "significant" if the rate fell by >= DROP_PP percentage points
# OR by >= DROP_REL percent relative to the prior month.
DROP_PP = 3.0
DROP_REL = 20.0
_RATE_STAGES = [
    ("submission_rate_pct", "submission", "Submission rate"),
    ("approval_rate_pct", "approval", "Approval rate"),
    ("completion_rate_pct", "completion", "Disbursement rate"),
]


def anomalies(pp: float = DROP_PP, rel: float = DROP_REL) -> list[dict]:
    """Significant month-over-month rate drops (latest vs previous month), each
    tagged with the funnel stage so the owner of that stage can be flagged."""
    r = rows()
    if len(r) < 2:
        return []
    latest, prev = r[-1], r[-2]
    out = []
    for key, stage, label in _RATE_STAGES:
        a, b = prev.get(key), latest.get(key)
        if a in (None, 0) or b is None:
            continue
        d_pp = round(b - a, 1)
        d_rel = round(100 * (b - a) / a, 1)
        if d_pp <= -pp or d_rel <= -rel:
            out.append({"stage": stage, "metric": label,
                        "prev_month": prev["month"], "prev_pct": a,
                        "latest_month": latest["month"], "latest_pct": b,
                        "delta_pp": d_pp, "delta_pct": d_rel})
    return out


def targets() -> dict:
    return _load().get("targets", {})


def target_misses(margin_pp: float = 1.0) -> list[dict]:
    """Stage rates that are below their OKR target in the latest month (the second
    flag trigger, alongside MoM drops). Tagged with stage for owner routing."""
    t = targets()
    if not t:
        return []
    latest = rows()[-1]
    out = []
    for key, stage, label in _RATE_STAGES:
        tgt, act = t.get(key), latest.get(key)
        if tgt is None or act is None:
            continue
        gap = round(act - tgt, 1)
        if gap <= -margin_pp:
            out.append({"stage": stage, "metric": label, "actual_pct": act,
                        "target_pct": tgt, "gap_pp": gap, "month": latest["month"]})
    return out


def _b(v):
    return f"{v / 1e9:.1f}B"


def _m(v):
    return f"{v / 1e6:.1f}M"


def _signed_int(v: int | float | None) -> str:
    if v is None:
        return ""
    try:
        v = int(round(v))
    except Exception:  # noqa: BLE001
        return str(v)
    return f"{v:+,}"


def _signed_amount(v: int | float | None) -> str:
    if v is None:
        return ""
    sign = "+" if v >= 0 else "-"
    return sign + _b(abs(v))


def _signed_m(v: int | float | None) -> str:
    if v is None:
        return ""
    sign = "+" if v >= 0 else "-"
    return sign + _m(abs(v))


def _mom_pct(curr: float | int | None, prev: float | int | None) -> str:
    if prev in (None, 0) or curr is None:
        return ""
    return f"{(100 * (curr - prev) / prev):+.0f}%"


def _mom_pp(curr: float | None, prev: float | None) -> str:
    if curr is None or prev is None:
        return ""
    return f"{(curr - prev):+.1f}pp"


def rows_upto(month: str) -> list[dict]:
    """Rows up to and including a YYYY-MM month; raises ValueError if not found."""
    data = rows()
    if not any(x["month"] == month for x in data):
        raise ValueError(f"month {month} not available")
    return [x for x in data if x["month"] <= month]


def _target_misses_for_rows(r: list[dict], margin_pp: float = 1.0) -> list[dict]:
    t = targets()
    if not t or not r:
        return []
    latest = r[-1]
    out = []
    for key, stage, label in _RATE_STAGES:
        tgt, act = t.get(key), latest.get(key)
        if tgt is None or act is None:
            continue
        gap = round(act - tgt, 1)
        if gap <= -margin_pp:
            out.append({"stage": stage, "metric": label, "actual_pct": act,
                        "target_pct": tgt, "gap_pp": gap, "month": latest["month"]})
    return out


def _anomalies_for_rows(r: list[dict], pp: float = DROP_PP, rel: float = DROP_REL) -> list[dict]:
    if len(r) < 2:
        return []
    latest, prev = r[-1], r[-2]
    out = []
    for key, stage, label in _RATE_STAGES:
        a, b = prev.get(key), latest.get(key)
        if a in (None, 0) or b is None:
            continue
        d_pp = round(b - a, 1)
        d_rel = round(100 * (b - a) / a, 1)
        if d_pp <= -pp or d_rel <= -rel:
            out.append({"stage": stage, "metric": label,
                        "prev_month": prev["month"], "prev_pct": a,
                        "latest_month": latest["month"], "latest_pct": b,
                        "delta_pp": d_pp, "delta_pct": d_rel})
    return out


def summary_for_month(month: str) -> dict:
    """Snapshot as if the requested month were the latest month.

    Used for prompts such as `show funnel metrics in April` so the agent does
    not answer with the latest May risk ranking.
    """
    r = rows_upto(month)
    latest, prev = (r[-1], r[-2]) if len(r) >= 2 else (r[-1], None)

    def delta(key):
        if not prev or latest.get(key) is None or prev.get(key) is None:
            return None
        return round(latest[key] - prev[key], 1)

    meta = _load()
    return {
        "partner": meta.get("partner"),
        "stages": STAGE_ORDER,
        "stage_definitions": meta.get("stage_definitions", {}),
        "latest_month": latest["month"],
        "latest": latest,
        "mom_pp": {
            "submission_rate": delta("submission_rate_pct"),
            "approval_rate": delta("approval_rate_pct"),
            "completion_rate": delta("completion_rate_pct"),
            "e2e_rate": delta("e2e_rate_pct"),
        },
        "months": r,
        "targets": targets(),
        "target_misses": _target_misses_for_rows(r),
        "anomalies": _anomalies_for_rows(r),
        "note": "Month-scoped snapshot. Treat this month as the latest month for risk ranking and MoM calculations.",
    }


def render_markdown(month: str | None = None) -> str:
    """Two LM-style tables with months as columns plus MoM columns.

    When month is supplied, render the table only up to that month and compute
    MoM vs the previous visible month.
    """
    r = rows_upto(month) if month else rows()
    months = [x["month"] for x in r]
    latest = r[-1]
    prev = r[-2] if len(r) >= 2 else None

    head = "| Metric | " + " | ".join(months) + " | MoM Abs | MoM Pct |"
    sep = "|---" * (len(months) + 3) + "|"

    def line(label, vals, mom_abs="", mom_pct=""):
        return "| " + label + " | " + " | ".join(vals) + f" | {mom_abs} | {mom_pct} |"

    def delta(key):
        if not prev:
            return None
        return latest.get(key, 0) - prev.get(key, 0)

    vol = [
        head, sep,
        line("Traffic (1)", [f"{x['traffic']:,}" for x in r], _signed_int(delta("traffic")), _mom_pct(latest.get("traffic"), prev.get("traffic") if prev else None)),
        line("Submission (2)", [f"{x['submission']:,}" for x in r], _signed_int(delta("submission")), _mom_pct(latest.get("submission"), prev.get("submission") if prev else None)),
        line("Approval (3)", [f"{x['approval']:,}" for x in r], _signed_int(delta("approval")), _mom_pct(latest.get("approval"), prev.get("approval") if prev else None)),
        line("Disbursement (4)", [f"{x['completion']:,}" for x in r], _signed_int(delta("completion")), _mom_pct(latest.get("completion"), prev.get("completion") if prev else None)),
        line("Disbursement Volume", [_b(x["completion_amount_vnd"]) for x in r], _signed_amount(delta("completion_amount_vnd")), _mom_pct(latest.get("completion_amount_vnd"), prev.get("completion_amount_vnd") if prev else None)),
        line("AVG Ticket Size", [_m(x["avg_ticket_vnd"]) for x in r], _signed_m(delta("avg_ticket_vnd")), _mom_pct(latest.get("avg_ticket_vnd"), prev.get("avg_ticket_vnd") if prev else None)),
    ]

    rate_head = head.replace("Metric", "Rate")
    rate = [
        rate_head, sep,
        line("Submission rate (2)/(1)", [f"{x['submission_rate_pct']}%" for x in r], _mom_pp(latest.get("submission_rate_pct"), prev.get("submission_rate_pct") if prev else None), _mom_pct(latest.get("submission_rate_pct"), prev.get("submission_rate_pct") if prev else None)),
        line("Approval rate (3)/(2)", [f"{x['approval_rate_pct']}%" for x in r], _mom_pp(latest.get("approval_rate_pct"), prev.get("approval_rate_pct") if prev else None), _mom_pct(latest.get("approval_rate_pct"), prev.get("approval_rate_pct") if prev else None)),
        line("Disbursement rate (4)/(3)", [f"{x['completion_rate_pct']}%" for x in r], _mom_pp(latest.get("completion_rate_pct"), prev.get("completion_rate_pct") if prev else None), _mom_pct(latest.get("completion_rate_pct"), prev.get("completion_rate_pct") if prev else None)),
        line("Traffic E2E (4)/(1)", [f"{x['e2e_rate_pct']}%" for x in r], _mom_pp(latest.get("e2e_rate_pct"), prev.get("e2e_rate_pct") if prev else None), _mom_pct(latest.get("e2e_rate_pct"), prev.get("e2e_rate_pct") if prev else None)),
    ]

    return ("**Funnel — monthly volumes**\n\n" + "\n".join(vol) +
            "\n\n**Conversion rates**\n\n" + "\n".join(rate))
