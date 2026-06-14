"""Structured initiative contracts.

A Jira task is more useful when it declares the metric it intends to move. These
helpers normalize model-extracted fields and render an auditable contract into
Jira descriptions. Any numeric impact should come from impact.py, not the LLM.
"""
from __future__ import annotations

import re
from datetime import datetime

ALLOWED_STAGES = {"traffic", "submission", "approval", "disbursement", "crosscut"}
STAGE_TO_METRIC = {
    "traffic": "eligible_traffic",
    "submission": "submission_rate_pct",
    "approval": "approval_rate_pct",
    "disbursement": "disbursement_rate_pct",
    "crosscut": "platform_reliability",
}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}


def _clean_text(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _clean_stage(v) -> str | None:
    s = (_clean_text(v) or "").lower().replace("-", "_")
    aliases = {
        "docs": "submission",
        "document": "submission",
        "documents": "submission",
        "review": "approval",
        "payout": "disbursement",
        "platform": "crosscut",
        "data": "crosscut",
    }
    s = aliases.get(s, s)
    return s if s in ALLOWED_STAGES else None


def _clean_due(v) -> str | None:
    s = _clean_text(v)
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _clean_float(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize(fields: dict | None, *, default_summary: str | None = None) -> dict:
    fields = fields or {}
    stage = _clean_stage(fields.get("stage"))
    metric = _clean_text(fields.get("metric")) or (STAGE_TO_METRIC.get(stage) if stage else None)
    confidence = (_clean_text(fields.get("confidence")) or "medium").lower()
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "medium"
    evidence = fields.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    evidence = [_clean_text(e) for e in evidence if _clean_text(e)][:8]
    expected_value = fields.get("expected_value_vnd")
    if expected_value is not None:
        try:
            expected_value = int(float(expected_value))
        except (TypeError, ValueError):
            expected_value = None
    return {
        "summary": _clean_text(fields.get("summary")) or default_summary or "Investigate funnel metric",
        "stage": stage,
        "metric": metric,
        "owner": _clean_text(fields.get("owner")),
        "due": _clean_due(fields.get("due")),
        "target_lift_pp": _clean_float(fields.get("target_lift_pp")),
        "expected_value_vnd": expected_value,
        "confidence": confidence,
        "evidence": evidence,
    }


def slug(s: str | None) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown"


def render_markdown(contract: dict, *, include_header: bool = True) -> str:
    lines = []
    if include_header:
        lines.append("# Initiative contract")
    lines.extend([
        f"- Stage: {contract.get('stage') or 'unknown'}",
        f"- Metric: {contract.get('metric') or 'unknown'}",
        f"- Owner: {contract.get('owner') or 'unassigned'}",
        f"- Due: {contract.get('due') or 'not set'}",
    ])
    if contract.get("target_lift_pp") is not None:
        lines.append(f"- Target lift: {contract['target_lift_pp']}pp")
    if contract.get("expected_value_vnd") is not None:
        lines.append(f"- Expected / at-risk value: {contract['expected_value_vnd']:,} VND")
    lines.append(f"- Confidence: {contract.get('confidence') or 'medium'}")
    if contract.get("evidence"):
        lines.append("\nEvidence:")
        for e in contract["evidence"]:
            lines.append(f"- {e}")
    lines.append("\nGuardrail: numbers and impact are computed by Funnel Watchtower; the LLM only drafted language around this contract.")
    return "\n".join(lines)


def from_ranked_problem(problem: dict, owner: str | None = None) -> dict:
    impact = problem.get("impact", {})
    stage = problem.get("stage")
    evidence = list(problem.get("signals", []))
    if impact.get("assumption"):
        evidence.append("Impact sizing: " + impact["assumption"])
    if problem.get("execution_risk"):
        er = problem["execution_risk"]
        evidence.append(
            f"Execution risk: {er.get('open_count', 0)} open, {er.get('blocked_count', 0)} blocked, {er.get('overdue_count', 0)} overdue"
        )
    return normalize({
        "summary": f"Investigate {str(stage).title()} funnel risk",
        "stage": stage,
        "metric": impact.get("metric"),
        "owner": owner,
        "expected_value_vnd": impact.get("value_at_risk_vnd"),
        "confidence": problem.get("confidence", "medium"),
        "evidence": evidence,
    })
