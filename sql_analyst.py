"""Read-only SQL analyst over application-level funnel data (DuckDB).

The configured LLM is useful for ad-hoc language, but the safest demo path is
"template first, LLM fallback". Common line-manager questions such as daily
volume, by-product, by-channel, drop reason, and approval-drop diagnostics use
known-good SQL templates. The model only writes SQL when no template matches;
all SQL is read-only validated and returned for auditability.
"""
from __future__ import annotations

import calendar
import os
import re

import report as rp

CSV = os.path.join(os.path.dirname(__file__), "data", "funnel_synthetic.csv")

_VIEW_SQL = """
CREATE OR REPLACE VIEW funnel AS
SELECT *,
  CASE final_stage WHEN 'applied' THEN 1 WHEN 'docs_submitted' THEN 2
       WHEN 'approved' THEN 3 WHEN 'disbursed' THEN 4 END AS stage_rank,
  CASE final_stage WHEN 'applied' THEN 'Traffic' WHEN 'docs_submitted' THEN 'Submission'
       WHEN 'approved' THEN 'Approval' WHEN 'disbursed' THEN 'Disbursement' END AS funnel_stage,
  CAST(applied_date AS DATE) AS applied_dt
FROM read_csv_auto('{csv}', header=true)
"""

SCHEMA_DOC = """Table `funnel` — one row per user who entered the application flow (synthetic). Columns:
- app_id (text)
- product_type: standard_application | premium_application | express_application | partner_application
- channel: web | mobile_app | agent_referral
- applied_date (text 'YYYY-MM-DD'); applied_dt (DATE) — use applied_dt for date math
- iso_week (int)
- requested_vnd (bigint) — requested amount in VND
- final_stage: applied | docs_submitted | approved | disbursed (furthest funnel stage reached)
- funnel_stage: Traffic | Submission | Approval | Disbursement (reconciled label; applied=Traffic
  means entered the flow but did not submit; docs_submitted=Submission, etc.)
- stage_rank: 1..4 (applied/Traffic=1, docs_submitted/Submission=2, approved/Approval=3, disbursed=4)
- drop_reason: '' when disbursed, else policy_check | docs_abandoned | docs_invalid | eligibility_check | customer_withdrew
Rules: a row REACHED stage N if stage_rank >= N. Disbursed = stage_rank = 4.
'May 2026' means applied_dt BETWEEN DATE '2026-05-01' AND DATE '2026-05-31'."""

_SELECT_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|copy|pragma|install|load|export|call)\b",
    re.IGNORECASE,
)
_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})


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
    if not _SELECT_ONLY.match(s) or _FORBIDDEN.search(s):
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
            return f"applied_dt BETWEEN DATE '{year}-{num:02d}-01' AND DATE '{year}-{num:02d}-{last:02d}'"
    ym = re.search(r"\b(20\d{2})-(\d{1,2})\b", q)
    if ym:
        y, m = int(ym.group(1)), int(ym.group(2))
        last = calendar.monthrange(y, m)[1]
        return f"applied_dt BETWEEN DATE '{y}-{m:02d}-01' AND DATE '{y}-{m:02d}-{last:02d}'"
    # Synthetic demo latest month.
    return "applied_dt BETWEEN DATE '2026-05-01' AND DATE '2026-05-31'"


def _stage_counts_expr() -> str:
    return (
        "COUNT(*) AS applications, "
        "SUM(CASE WHEN stage_rank >= 2 THEN 1 ELSE 0 END) AS submitted, "
        "SUM(CASE WHEN stage_rank >= 3 THEN 1 ELSE 0 END) AS approved, "
        "SUM(CASE WHEN stage_rank = 4 THEN 1 ELSE 0 END) AS disbursed, "
        "ROUND(100.0 * SUM(CASE WHEN stage_rank >= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 1) AS submission_rate_pct, "
        "ROUND(100.0 * SUM(CASE WHEN stage_rank >= 3 THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN stage_rank >= 2 THEN 1 ELSE 0 END),0), 1) AS approval_rate_pct, "
        "ROUND(100.0 * SUM(CASE WHEN stage_rank = 4 THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN stage_rank >= 3 THEN 1 ELSE 0 END),0), 1) AS disbursement_rate_pct"
    )


def template_sql(question: str) -> tuple[str | None, str | None]:
    """Return (sql, template_name) for common safe questions."""
    q = question.lower()
    where = _month_filter(question)
    counts = _stage_counts_expr()

    if any(k in q for k in ["why", "root cause", "diagnose", "diagnostic", "approval drop", "approval fell"]):
        sql = f"""
WITH scoped AS (SELECT * FROM funnel WHERE {where})
SELECT 'product_type' AS dimension, product_type AS segment, {counts}
FROM scoped GROUP BY product_type
UNION ALL
SELECT 'channel' AS dimension, channel AS segment, {counts}
FROM scoped GROUP BY channel
UNION ALL
SELECT 'drop_reason' AS dimension, COALESCE(NULLIF(drop_reason, ''), 'disbursed') AS segment, {counts}
FROM scoped GROUP BY COALESCE(NULLIF(drop_reason, ''), 'disbursed')
ORDER BY dimension, applications DESC
"""
        return sql, "diagnostic_contribution"

    if any(k in q for k in ["daily", "by day", "per day", "day by day", "each day"]):
        return f"""
SELECT applied_dt AS day, {counts}, SUM(requested_vnd) AS requested_vnd
FROM funnel
WHERE {where}
GROUP BY applied_dt
ORDER BY applied_dt
""", "daily_volume"

    if "week" in q or "weekly" in q:
        return f"""
SELECT iso_week, {counts}, SUM(requested_vnd) AS requested_vnd
FROM funnel
WHERE {where}
GROUP BY iso_week
ORDER BY iso_week
""", "weekly_volume"

    if "drop reason" in q or "by drop" in q:
        return f"""
SELECT COALESCE(NULLIF(drop_reason, ''), 'disbursed') AS drop_reason, COUNT(*) AS applications,
       SUM(CASE WHEN stage_rank = 4 THEN 1 ELSE 0 END) AS disbursed,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct
FROM funnel
WHERE {where}
GROUP BY COALESCE(NULLIF(drop_reason, ''), 'disbursed')
ORDER BY applications DESC
""", "drop_reason_breakdown"

    if "product" in q or "segment" in q:
        return f"""
SELECT product_type, {counts}, SUM(requested_vnd) AS requested_vnd
FROM funnel
WHERE {where}
GROUP BY product_type
ORDER BY applications DESC
""", "product_breakdown"

    if "channel" in q:
        return f"""
SELECT channel, {counts}, SUM(requested_vnd) AS requested_vnd
FROM funnel
WHERE {where}
GROUP BY channel
ORDER BY applications DESC
""", "channel_breakdown"

    if "volume" in q or "count" in q or "how many" in q:
        return f"""
SELECT {counts}, SUM(requested_vnd) AS requested_vnd
FROM funnel
WHERE {where}
""", "total_volume"

    return None, None


def write_sql(question: str) -> str | None:
    """Ask the LLM for a single SELECT. Returns None when the LLM is unavailable."""
    out = rp.llm_chat(
        "You are a SQL analyst. Write ONE read-only DuckDB SELECT that answers the user's "
        "question against this schema. Return ONLY the SQL — no prose, no code fences. "
        "Prefer simple grouped aggregates.\n\n" + SCHEMA_DOC,
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
    stage = "approval"
    if "submission" in q:
        stage = "submission"
    elif "disbursement" in q:
        stage = "disbursement"

    metric_col = {
        "submission": "submission_rate_pct",
        "approval": "approval_rate_pct",
        "disbursement": "disbursement_rate_pct",
    }[stage]
    metric_label = metric_col.replace("_", " ").replace(" pct", "")

    sql, template = template_sql(f"diagnose {stage} drop by product channel drop reason")
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
                findings.append(f"{row[dim_i]}={row[seg_i]}: {row[apps_i]} applications, {metric_label} {row[rate_i]}%")
        except Exception:  # noqa: BLE001
            pass
    return {"stage": stage, "template": template, "metric": metric_col, "sql": sql, "result": res, "top_findings": findings, "highlights": findings}
