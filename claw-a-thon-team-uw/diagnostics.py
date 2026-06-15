"""Deterministic diagnostic templates over the application-level funnel CSV.

The goal is not to claim causality. We use contribution-style slices to show
where a stage-rate drop is concentrated. The LLM may explain these rows, but
SQL templates produce the numbers.
"""
from __future__ import annotations

import calendar
import os
import re
from datetime import datetime

import funnel_metrics as fm
import sql_analyst as sa

_STAGE = {
    "submission": {
        "label": "Submission",
        "denom": "stage_rank >= 1",
        "passed": "stage_rank >= 2",
        "failed": "stage_rank = 1",
        "rate": "submission_rate_pct",
    },
    "approval": {
        "label": "Approval",
        "denom": "stage_rank >= 2",
        "passed": "stage_rank >= 3",
        "failed": "stage_rank = 2",
        "rate": "approval_rate_pct",
    },
    "completion": {
        "label": "Disbursement",
        "denom": "stage_rank >= 3",
        "passed": "stage_rank = 4",
        "failed": "stage_rank = 3",
        "rate": "completion_rate_pct",
    },
}

_DIMENSIONS = ("product_type", "channel")


def configured() -> bool:
    return sa.configured()


def _latest_months() -> tuple[str, str]:
    rows = fm.rows()
    if len(rows) >= 2:
        return rows[-1]["month"], rows[-2]["month"]
    return rows[-1]["month"], rows[-1]["month"]


def _month_bounds(month: str) -> tuple[str, str]:
    dt = datetime.strptime(month, "%Y-%m")
    last = calendar.monthrange(dt.year, dt.month)[1]
    return f"{month}-01", f"{month}-{last:02d}"


def _detect_stage(text: str) -> str | None:
    low = text.lower()
    for stage in _STAGE:
        if stage in low:
            return stage
    if "submit" in low or "docs" in low or "document" in low:
        return "submission"
    if "approve" in low or "underwrit" in low or "declin" in low or "reject" in low:
        return "approval"
    if "completion" in low or "complete" in low or "completed" in low or "payout" in low:
        return "completion"
    return None


def _wants_diagnostic(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in (
        "why", "root cause", "diagnose", "diagnostic", "contribution", "driver",
        "drill", "localize", "where is", "what caused", "drop reason", "reason"
    )) and any(w in low for w in ("drop", "dropped", "down", "decline", "miss", "below", "reason", "cause"))


def _safe_dimension(dimension: str) -> str:
    if dimension not in _DIMENSIONS:
        raise ValueError("unsupported dimension")
    return dimension


def dimension_sql(stage: str, dimension: str, current: str | None = None, previous: str | None = None) -> str:
    stage = stage.lower()
    cfg = _STAGE[stage]
    dimension = _safe_dimension(dimension)
    current, previous = current or _latest_months()[0], previous or _latest_months()[1]
    return f"""
WITH scoped AS (
  SELECT
    CASE
      WHEN strftime(entered_dt, '%Y-%m') = '{current}' THEN 'current'
      WHEN strftime(entered_dt, '%Y-%m') = '{previous}' THEN 'previous'
    END AS period,
    {dimension} AS segment,
    CASE WHEN {cfg['passed']} THEN 1 ELSE 0 END AS passed
  FROM funnel
  WHERE ({cfg['denom']})
    AND strftime(entered_dt, '%Y-%m') IN ('{previous}', '{current}')
), agg AS (
  SELECT segment, period, COUNT(*) AS denominator, SUM(passed) AS passed
  FROM scoped
  WHERE period IS NOT NULL
  GROUP BY segment, period
), pivoted AS (
  SELECT
    segment,
    SUM(CASE WHEN period = 'previous' THEN denominator ELSE 0 END) AS prev_denominator,
    SUM(CASE WHEN period = 'previous' THEN passed ELSE 0 END) AS prev_passed,
    SUM(CASE WHEN period = 'current' THEN denominator ELSE 0 END) AS current_denominator,
    SUM(CASE WHEN period = 'current' THEN passed ELSE 0 END) AS current_passed
  FROM agg
  GROUP BY segment
)
SELECT
  segment,
  prev_denominator,
  current_denominator,
  ROUND(100.0 * prev_passed / NULLIF(prev_denominator, 0), 1) AS prev_rate_pct,
  ROUND(100.0 * current_passed / NULLIF(current_denominator, 0), 1) AS current_rate_pct,
  ROUND(100.0 * current_passed / NULLIF(current_denominator, 0)
        - 100.0 * prev_passed / NULLIF(prev_denominator, 0), 1) AS delta_pp,
  ROUND(100.0 * current_denominator / NULLIF(SUM(current_denominator) OVER (), 0), 1) AS current_volume_share_pct,
  ROUND(ABS((100.0 * current_passed / NULLIF(current_denominator, 0)
        - 100.0 * prev_passed / NULLIF(prev_denominator, 0))) * current_denominator, 1) AS contribution_score
FROM pivoted
WHERE current_denominator > 0 OR prev_denominator > 0
ORDER BY contribution_score DESC
LIMIT 8
""".strip()


def drop_reason_sql(stage: str, current: str | None = None) -> str:
    cfg = _STAGE[stage.lower()]
    current = current or _latest_months()[0]
    start, end = _month_bounds(current)
    return f"""
SELECT
  COALESCE(NULLIF(drop_reason, ''), 'n/a') AS drop_reason,
  COUNT(*) AS applications,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
  SUM(potential_value_vnd) AS potential_value_vnd
FROM funnel
WHERE entered_dt BETWEEN DATE '{start}' AND DATE '{end}'
  AND ({cfg['failed']})
GROUP BY 1
ORDER BY applications DESC
LIMIT 8
""".strip()


def _run(sql: str) -> dict:
    res = sa.run_sql(sql)
    res["sql"] = sql
    return res


def stage_diagnostics(stage: str, current: str | None = None, previous: str | None = None) -> dict:
    """Return contribution-style diagnostics for a stage."""
    stage = stage.lower()
    if stage not in _STAGE:
        return {"error": f"unsupported stage: {stage}"}
    if not configured():
        return {"error": "diagnostic dataset is unavailable"}
    current, previous = current or _latest_months()[0], previous or _latest_months()[1]
    by_dimension = {}
    sqls = {}
    for dimension in _DIMENSIONS:
        sql = dimension_sql(stage, dimension, current, previous)
        by_dimension[dimension] = _run(sql)
        sqls[dimension] = sql
    dr_sql = drop_reason_sql(stage, current)
    drop_reasons = _run(dr_sql)
    return {
        "stage": stage,
        "metric": _STAGE[stage]["label"],
        "current_month": current,
        "previous_month": previous,
        "interpretation_note": "Contribution rows identify where the drop is concentrated; they do not prove causality.",
        "by_dimension": by_dimension,
        "drop_reasons": drop_reasons,
        "sql_templates": sqls | {"drop_reasons": dr_sql},
    }


def _rows(res: dict) -> list[dict]:
    if res.get("error") or not res.get("rows"):
        return []
    cols = res.get("columns") or []
    return [dict(zip(cols, r)) for r in res.get("rows", [])]


def render_markdown(diag: dict) -> str:
    if diag.get("error"):
        return f"I couldn't run diagnostics: {diag['error']}"
    stage = diag["stage"].title()
    out = [f"## {stage} diagnostic ({diag['previous_month']} → {diag['current_month']})",
           "_This is contribution analysis, not causal proof._"]
    for dimension, res in diag.get("by_dimension", {}).items():
        out.append(f"\n### By {dimension.replace('_', ' ')}")
        out.append(sa.to_markdown(res, max_rows=8))
    out.append("\n### Current-month drop reasons")
    out.append(sa.to_markdown(diag.get("drop_reasons", {}), max_rows=8))
    return "\n".join(out)


def try_answer(question: str) -> dict | None:
    """Return a diagnostic answer when the user asks for root-cause/drilldown."""
    if not configured():
        return None
    stage = _detect_stage(question)
    if not stage or not _wants_diagnostic(question):
        return None
    diag = stage_diagnostics(stage)
    diag["markdown"] = render_markdown(diag)
    return diag
