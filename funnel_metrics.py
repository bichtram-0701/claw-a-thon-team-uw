"""Funnel performance metrics — Funnel Watchtower, Team UW.

Loads the synthetic row-level funnel fixture and computes monthly conversion rates
between stages (Traffic -> Submission -> Approval -> Completion), average
outcome value, and month-over-month deltas. Deterministic: the LLM narrates
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
    """Per-month volumes + derived rates + average outcome value.

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
                "completion=completion/approval, e2e=completion/traffic.",
    }


# A drop counts as "significant" if the rate fell by >= DROP_PP percentage points
# OR by >= DROP_REL percent relative to the prior month.
DROP_PP = 3.0
DROP_REL = 20.0
_RATE_STAGES = [
    ("submission_rate_pct", "submission", "Submission rate"),
    ("approval_rate_pct", "approval", "Approval rate"),
    ("completion_rate_pct", "completion", "Completion rate"),
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
           line("Completion", [f"{x['completion']:,}" for x in r]),
           line("Completion value (VND)", [_b(x["completion_amount_vnd"]) for x in r]),
           line("Avg outcome value (VND)", [_m(x["avg_ticket_vnd"]) for x in r])]

    rate = [head.replace("Metric", "Rate"), sep,
            line("Submission (Sub/Traffic)", [f"{x['submission_rate_pct']}%" for x in r]),
            line("Approval (Appr/Sub)", [f"{x['approval_rate_pct']}%" for x in r]),
            line("Completion (Comp/Appr)", [f"{x['completion_rate_pct']}%" for x in r]),
            line("Traffic E2E (Comp/Traffic)", [f"{x['e2e_rate_pct']}%" for x in r])]

    return ("**Funnel — monthly volumes**\n\n" + "\n".join(vol) +
            "\n\n**Conversion rates**\n\n" + "\n".join(rate))
