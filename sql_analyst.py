"""Read-only SQL analyst over application-level funnel data (DuckDB).

The safe demo path is template first, LLM fallback. Common line-manager
questions such as daily volume, by-product, by-channel, approval-drop reasons,
and contribution diagnostics use known-good SQL templates. The model only writes
SQL when no template matches; all SQL is read-only validated and returned for
auditability.
"""
from __future__ import annotations

import calendar
import os
import re

import report as rp

CSV = os.path.join(os.path.dirname(__file__), "data", "funnel_synthetic.csv")

_VIEW_SQL = """
CREATE OR REPLACE VIEW funnel AS
SELECT
  entity_id,
  entity_id AS app_id,              -- compatibility alias for older prompts/docs
  product_type,
  channel,
  entered_date,
  CAST(entered_date AS DATE) AS entered_dt,
  entered_date AS applied_date,      -- compatibility alias for older templates
  CAST(entered_date AS DATE) AS applied_dt,
  iso_week,
  potential_value_vnd,
  potential_value_vnd AS requested_vnd,
  final_stage,
  drop_transition,
  drop_reason,
  CASE final_stage
    WHEN 'traffic' THEN 1
    WHEN 'submitted' THEN 2
    WHEN 'approved' THEN 3
    WHEN 'completed' THEN 4
  END AS stage_rank,
  CASE final_stage
    WHEN 'traffic' THEN 'Traffic'
    WHEN 'submitted' THEN 'Submission'
    WHEN 'approved' THEN 'Approval'
    WHEN 'completed' THEN 'Completion'
  END AS funnel_stage
FROM read_csv_auto('{csv}', header=true)
"""

SCHEMA_DOC = """Table `funnel` — one row per distinct synthetic user/entity that entered the funnel.
Columns:
- entity_id (text); app_id is available as a backward-compatible alias
- product_type: standard_application | premium_application | express_application | partner_application
- channel: web | mobile_app | agent_referral
- entered_date (text 'YYYY-MM-DD'); entered_dt (DATE) — use entered_dt for date math
- iso_week (int)
- potential_value_vnd (bigint) — synthetic potential/completed value in VND
- final_stage: traffic | submitted | approved | completed (furthest funnel stage reached)
- funnel_stage: Traffic | Submission | Approval | Completion
- stage_rank: 1..4 (traffic=1, submitted=2, approved=3, completed=4)
- drop_transition: traffic_to_submission | submission_to_approval | approval_to_completion | blank when completed
- drop_reason: blank only when completed. It explains why the user/entity failed to reach the next stage.
Counting rules:
- traffic/users = COUNT(*)
- submitted = COUNT(stage_rank >= 2)
- approved = COUNT(stage_rank >= 3)
- completed = COUNT(stage_rank = 4)
- approval drops = COUNT(stage_rank = 2), which equals submitted - approved.
'May 2026' means entered_dt BETWEEN DATE '2026-05-01' AND DATE '2026-05-31'."""


def schema_guide_markdown() -> str:
    """Short user-facing guide for database-style questions."""
    return (
        "You can ask database-style questions using the `funnel` view. I run safe read-only SQL templates first, "
        "and only use LLM-written SELECTs as a fallback.\n\n"
        "**Useful columns:** `entity_id`, `entered_dt`, `product_type`, `channel`, `final_stage`, "
        "`stage_rank`, `drop_transition`, `drop_reason`, `potential_value_vnd`.\n\n"
        "**Counting rules:** Traffic = `COUNT(*)`; Submission = `COUNT(stage_rank >= 2)`; "
        "Approval = `COUNT(stage_rank >= 3)`; Completion = `COUNT(stage_rank = 4)`.\n\n"
        "**Good prompts:** `/query show daily volume in May`, `/query break May approval drop down by reason`, "
        "`show May by product`, `show May by channel`, `why did approval drop?`, or "
        "`/query break May drop reasons by transition`."
    )

_SELECT_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|copy|pragma|install|load|export|call)\b",
    re.IGNORECASE,
)


def _strip_sql_literals(sql: str) -> str:
    """Remove quoted strings before forbidden-keyword checks.

    This avoids false positives for audit labels such as 'Submission -> Approval drop'
    while still blocking actual DDL/DML commands.
    """
    return re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "''", sql)
_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})

_STAGE_LOSSES = {
    "submission": {
        "label": "Traffic -> Submission drop",
        "loss_key": "traffic_to_submission",
        "failed": "stage_rank = 1",
        "stage_start": "stage_rank >= 1",
        "stage_passed": "stage_rank >= 2",
        "rate_col": "submission_rate_pct",
        "denom": "stage_rank >= 1",
        "passed": "stage_rank >= 2",
    },
    "approval": {
        "label": "Submission -> Approval drop",
        "loss_key": "submission_to_approval",
        "failed": "stage_rank = 2",
        "stage_start": "stage_rank >= 2",
        "stage_passed": "stage_rank >= 3",
        "rate_col": "approval_rate_pct",
        "denom": "stage_rank >= 2",
        "passed": "stage_rank >= 3",
    },
    "completion": {
        "label": "Approval -> Completion drop",
        "loss_key": "approval_to_completion",
        "failed": "stage_rank = 3",
        "stage_start": "stage_rank >= 3",
        "stage_passed": "stage_rank = 4",
        "rate_col": "completion_rate_pct",
        "denom": "stage_rank >= 3",
        "passed": "stage_rank = 4",
    },
}


def _cell(v):
    from datetime import date, datetime
    from decimal import Decimal
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return v


def configured() -> bool:
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return False
    return os.path.exists(CSV)


def _con():
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute(_VIEW_SQL.format(csv=CSV.replace("'", "''")))
    return con


def run_sql(sql: str, limit: int = 200) -> dict:
    """Execute a single read-only SELECT/WITH against the `funnel` view."""
    s = (sql or "").strip().rstrip(";").strip()
    if not _SELECT_ONLY.match(s) or _FORBIDDEN.search(_strip_sql_literals(s)):
        return {"error": "only a single read-only SELECT/WITH is allowed"}
    if ";" in s:
        return {"error": "multiple statements are not allowed"}
    try:
        con = _con()
        cur = con.execute(s)
        cols = [d[0] for d in cur.description]
        rows = [[_cell(v) for v in r] for r in cur.fetchmany(limit)]
        con.close()
        return {"columns": cols, "rows": rows}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:240]}


def to_markdown(res: dict, max_rows: int = 50) -> str:
    if res.get("error"):
        return f"(query error: {res['error']})"
    cols, rows = res["columns"], res["rows"]
    if not rows:
        return "(no rows matched)"
    head = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "|" + "---|" * len(cols)
    body = ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows[:max_rows]]
    extra = f"\n\n_({len(rows)} rows; showing {max_rows})_" if len(rows) > max_rows else ""
    return "\n".join([head, sep] + body) + extra


def _month_filter(question: str) -> str:
    q = question.lower()
    year_m = re.search(r"\b(20\d{2})\b", q)
    year = int(year_m.group(1)) if year_m else 2026
    for name, num in _MONTHS.items():
        if re.search(rf"\b{name}\b", q):
            last = calendar.monthrange(year, num)[1]
            return f"entered_dt BETWEEN DATE '{year}-{num:02d}-01' AND DATE '{year}-{num:02d}-{last:02d}'"
    ym = re.search(r"\b(20\d{2})-(\d{1,2})\b", q)
    if ym:
        y, m = int(ym.group(1)), int(ym.group(2))
        last = calendar.monthrange(y, m)[1]
        return f"entered_dt BETWEEN DATE '{y}-{m:02d}-01' AND DATE '{y}-{m:02d}-{last:02d}'"
    # Synthetic demo latest month.
    return "entered_dt BETWEEN DATE '2026-05-01' AND DATE '2026-05-31'"


def _stage_counts_expr() -> str:
    return (
        "COUNT(*) AS applications, "
        "SUM(CASE WHEN stage_rank >= 2 THEN 1 ELSE 0 END) AS submitted, "
        "SUM(CASE WHEN stage_rank >= 3 THEN 1 ELSE 0 END) AS approved, "
        "SUM(CASE WHEN stage_rank = 4 THEN 1 ELSE 0 END) AS completed, "
        "ROUND(100.0 * SUM(CASE WHEN stage_rank >= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 1) AS submission_rate_pct, "
        "ROUND(100.0 * SUM(CASE WHEN stage_rank >= 3 THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN stage_rank >= 2 THEN 1 ELSE 0 END),0), 1) AS approval_rate_pct, "
        "ROUND(100.0 * SUM(CASE WHEN stage_rank = 4 THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN stage_rank >= 3 THEN 1 ELSE 0 END),0), 1) AS completion_rate_pct"
    )


def _amount_expr() -> str:
    return (
        "SUM(potential_value_vnd) AS potential_value_vnd, "
        "SUM(CASE WHEN stage_rank = 4 THEN potential_value_vnd ELSE 0 END) AS completion_amount_vnd"
    )


def _detect_drop_stage(q: str) -> str:
    """Default generic drop-reason questions to approval, the current demo risk."""
    if any(k in q for k in ["traffic", "submission drop", "submit drop", "not submit", "not submitted"]):
        return "submission"
    if any(k in q for k in ["completion", "complete", "completed", "final outcome", "payout"]):
        return "completion"
    return "approval"


def _drop_reason_sql(where: str, stage: str) -> str:
    cfg = _STAGE_LOSSES[stage]
    return f"""
WITH scoped AS (
  SELECT * FROM funnel WHERE {where}
), totals AS (
  SELECT
    SUM(CASE WHEN {cfg['stage_start']} THEN 1 ELSE 0 END) AS stage_start_total,
    SUM(CASE WHEN {cfg['stage_passed']} THEN 1 ELSE 0 END) AS stage_passed_total,
    SUM(CASE WHEN {cfg['failed']} THEN 1 ELSE 0 END) AS stage_drop_total
  FROM scoped
)
SELECT
  '{cfg['label']}' AS loss_stage,
  COALESCE(NULLIF(drop_reason, ''), 'unknown') AS drop_reason,
  COUNT(*) AS dropped_applications,
  totals.stage_start_total,
  totals.stage_passed_total,
  totals.stage_drop_total,
  ROUND(100.0 * COUNT(*) / NULLIF(totals.stage_drop_total, 0), 1) AS share_of_stage_drop_pct
FROM scoped
CROSS JOIN totals
WHERE {cfg['failed']}
GROUP BY 1, 2, 4, 5, 6
ORDER BY dropped_applications DESC
"""


def _all_drop_reason_sql(where: str) -> str:
    return f"""
WITH scoped AS (
  SELECT * FROM funnel WHERE {where}
), losses AS (
  SELECT
    CASE
      WHEN stage_rank = 1 THEN 'Traffic -> Submission drop'
      WHEN stage_rank = 2 THEN 'Submission -> Approval drop'
      WHEN stage_rank = 3 THEN 'Approval -> Completion drop'
    END AS loss_stage,
    COALESCE(NULLIF(drop_reason, ''), 'unknown') AS drop_reason
  FROM scoped
  WHERE stage_rank < 4
)
SELECT
  loss_stage,
  drop_reason,
  COUNT(*) AS dropped_applications,
  ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY loss_stage), 0), 1) AS share_of_loss_stage_pct
FROM losses
GROUP BY loss_stage, drop_reason
ORDER BY loss_stage, dropped_applications DESC
"""


def _stage_diagnostic_sql(where: str, stage: str) -> str:
    cfg = _STAGE_LOSSES[stage]
    rate_col = cfg["rate_col"]
    counts = (
        "COUNT(*) AS applications, "
        f"SUM(CASE WHEN {cfg['passed']} THEN 1 ELSE 0 END) AS stage_passed_total, "
        f"SUM(CASE WHEN {cfg['failed']} THEN 1 ELSE 0 END) AS stage_dropped_total, "
        f"ROUND(100.0 * SUM(CASE WHEN {cfg['passed']} THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 1) AS {rate_col}"
    )
    denom = cfg["denom"]
    return f"""
WITH scoped AS (SELECT * FROM funnel WHERE {where} AND ({denom}))
SELECT 'product_type' AS dimension, product_type AS segment, {counts}
FROM scoped GROUP BY product_type
UNION ALL
SELECT 'channel' AS dimension, channel AS segment, {counts}
FROM scoped GROUP BY channel
ORDER BY dimension, applications DESC
"""


def template_sql(question: str) -> tuple[str | None, str | None]:
    """Return (sql, template_name) for common safe questions."""
    q = question.lower()
    where = _month_filter(question)
    counts = _stage_counts_expr()
    amounts = _amount_expr()

    # Drop reason questions should explain the relevant loss stage, not include successful rows.
    # Examples: "break May down by drop reason", "break May approval drop down by reason".
    asks_reason_breakdown = (
        "drop reason" in q
        or "by drop" in q
        or "reason breakdown" in q
        or "by reason" in q
        or "down by reason" in q
        or ("reason" in q and any(k in q for k in ["break", "breakdown", "break down"]) and any(k in q for k in ["drop", "dropped", "leak", "loss"]))
    )
    if asks_reason_breakdown:
        if any(k in q for k in ["all", "overall", "every stage", "all stages", "by transition"]):
            return _all_drop_reason_sql(where), "all_drop_reason_breakdown"
        stage = _detect_drop_stage(q)
        return _drop_reason_sql(where, stage), f"{stage}_drop_reason_breakdown"

    if any(k in q for k in ["daily", "by day", "per day", "day by day", "each day", "day over day", "day-over-day"]):
        return f"""
SELECT entered_dt AS day, {counts}, {amounts}
FROM funnel
WHERE {where}
GROUP BY entered_dt
ORDER BY entered_dt
""", "daily_volume"

    if "week" in q or "weekly" in q:
        return f"""
SELECT iso_week, {counts}, {amounts}
FROM funnel
WHERE {where}
GROUP BY iso_week
ORDER BY iso_week
""", "weekly_volume"

    if any(k in q for k in ["why", "root cause", "diagnose", "diagnostic", "approval drop", "approval fell", "driver", "contribution"]):
        stage = _detect_drop_stage(q)
        return _stage_diagnostic_sql(where, stage), f"{stage}_diagnostic_contribution"

    if "product" in q or "segment" in q:
        return f"""
SELECT product_type, {counts}, {amounts}
FROM funnel
WHERE {where}
GROUP BY product_type
ORDER BY applications DESC
""", "product_breakdown"

    if "channel" in q:
        return f"""
SELECT channel, {counts}, {amounts}
FROM funnel
WHERE {where}
GROUP BY channel
ORDER BY applications DESC
""", "channel_breakdown"

    if "volume" in q or "count" in q or "how many" in q or "number" in q:
        return f"""
SELECT {counts}, {amounts}
FROM funnel
WHERE {where}
""", "total_volume"

    return None, None


def write_sql(question: str) -> str | None:
    """Ask the LLM for a single SELECT. Returns None when the LLM is unavailable."""
    out = rp.llm_chat(
        "You are a SQL analyst. Write ONE read-only DuckDB SELECT that answers the user's "
        "question against this schema. Return ONLY the SQL — no prose, no code fences. "
        "Prefer simple grouped aggregates and the counting rules in the schema.\n\n" + SCHEMA_DOC,
        question,
        max_tokens=360,
        temperature=0.0,
        profile="reasoning",
    )
    if not out:
        return None
    sql = out.strip().strip("`").strip()
    sql = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    sql = re.sub(r"^sql\s+", "", sql, flags=re.IGNORECASE).strip()
    return sql


def answer(question: str) -> dict:
    """Template SQL -> run; otherwise LLM SQL -> run. Return rows + SQL."""
    sql, template = template_sql(question)
    source = "template" if sql else "llm"
    if not sql:
        sql = write_sql(question)
    if not sql:
        return {"error": "the analyst model is unavailable and no safe template matched", "sql": None}
    res = run_sql(sql)
    res["sql"] = sql
    res["source"] = source
    if template:
        res["template"] = template
    return res


# Compatibility helper for Jira investigation descriptions.
def diagnostic_findings(question: str, max_findings: int = 3) -> dict:
    """Run deterministic contribution analysis and return short evidence bullets."""
    q = (question or "").lower()
    stage = _detect_drop_stage(q)

    metric_col = _STAGE_LOSSES[stage]["rate_col"]
    metric_label = metric_col.replace("_", " ").replace(" pct", "")

    sql, template = template_sql(f"diagnose {stage} drop by product and channel")
    if not sql:
        return {"error": "no diagnostic template matched", "stage": stage, "top_findings": [], "highlights": []}
    res = run_sql(sql)
    findings: list[str] = []
    if not res.get("error"):
        cols = res.get("columns", [])
        try:
            dim_i = cols.index("dimension")
            seg_i = cols.index("segment")
            apps_i = cols.index("applications")
            rate_i = cols.index(metric_col)
            rows = sorted(res.get("rows", []), key=lambda r: (r[dim_i], -(r[apps_i] or 0)))
            for row in rows[:max_findings]:
                findings.append(f"{row[dim_i]}={row[seg_i]}: {row[apps_i]} stage-start applications, {metric_label} {row[rate_i]}%")
        except Exception:  # noqa: BLE001
            pass
    return {"stage": stage, "template": template, "metric": metric_col, "sql": sql, "result": res, "top_findings": findings, "highlights": findings}
