"""Read-only SQL analyst over the application-level funnel data (DuckDB).

For open-ended questions the canned metrics can't answer — "break May down by
day", "by drop reason", "by product/channel" — the LLM writes a single SELECT,
we run it against a reconciled view, and return the rows PLUS the SQL (auditable).
The numbers come from the query engine, not the model, so they can't be invented;
the only failure mode is wrong query logic, which is visible because we show the SQL.

Read-only: a single SELECT is allowed; anything else is rejected.
"""
import os
import re

import report as rp   # report.llm_chat (offline-safe: returns None when no LLM)

CSV = os.path.join(os.path.dirname(__file__), "data", "funnel_synthetic.csv")

# Reconcile the CSV's final_stage to the funnel model. The CSV is APPLICATION-level
# (no pre-application Traffic), so it covers Application -> Submission -> Approval
# -> Disbursement. A row "reached" stage N if stage_rank >= N.
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

SCHEMA_DOC = """Table `funnel` — one row per user who entered the lending flow (synthetic). Columns:
- app_id (text)
- product_type: motorbike_loan | personal_loan | salary_advance | consumer_durable
- channel: web | mobile_app | agent_referral
- applied_date (text 'YYYY-MM-DD'); applied_dt (DATE) — use applied_dt for date math
- iso_week (int)
- requested_vnd (bigint) — requested amount in VND
- final_stage: applied | docs_submitted | approved | disbursed (furthest funnel stage reached)
- funnel_stage: Traffic | Submission | Approval | Disbursement (reconciled label; applied=Traffic
  means entered the flow but did not submit; docs_submitted=Submission, etc.)
- stage_rank: 1..4 (applied/Traffic=1, docs_submitted/Submission=2, approved/Approval=3, disbursed/Disbursement=4)
- drop_reason: '' when disbursed, else credit_policy | docs_abandoned | docs_invalid | income_verification | customer_withdrew
Rules: a row REACHED stage N if stage_rank >= N. Disbursed = stage_rank = 4.
'May 2026' means applied_dt BETWEEN DATE '2026-05-01' AND DATE '2026-05-31'."""

_SELECT_ONLY = re.compile(r"^\s*select\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|copy|pragma|install|load|export|call)\b",
    re.IGNORECASE)


def _cell(v):
    """Make a DuckDB value JSON-serializable (dates -> ISO, Decimal -> float)."""
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
    """Execute a single read-only SELECT against the `funnel` view."""
    s = (sql or "").strip().rstrip(";").strip()
    if not _SELECT_ONLY.match(s) or _FORBIDDEN.search(s):
        return {"error": "only a single read-only SELECT is allowed"}
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
        return {"error": str(e)[:200]}


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


def write_sql(question: str) -> str | None:
    """Ask the LLM for a single SELECT. Returns None when the LLM is unavailable."""
    out = rp.llm_chat(
        "You are a SQL analyst. Write ONE read-only DuckDB SELECT that answers the user's "
        "question against this schema. Return ONLY the SQL — no prose, no code fences.\n\n"
        + SCHEMA_DOC,
        question, max_tokens=300)
    if not out:
        return None
    sql = out.strip().strip("`").strip()
    sql = re.sub(r"^sql\s+", "", sql, flags=re.IGNORECASE).strip()  # drop a ```sql tag
    return sql


def answer(question: str) -> dict:
    """Full path: LLM writes SQL -> run it -> return rows + the SQL."""
    sql = write_sql(question)
    if not sql:
        return {"error": "the analyst model is unavailable to write the query", "sql": None}
    res = run_sql(sql)
    res["sql"] = sql
    return res
