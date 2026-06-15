"""Structured initiative contracts for Jira issues.

A contract makes every recovery initiative measurable: which funnel stage and
metric it targets, what lift/value is expected, who owns it, and what evidence
was used. The LLM can narrate the contract, but code owns validation.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

ALLOWED_STAGES = {"traffic", "submission", "approval", "completion", "crosscut"}
STAGE_METRIC = {
    "submission": "submission_rate_pct",
    "approval": "approval_rate_pct",
    "completion": "completion_rate_pct",
    "traffic": "traffic_volume",
    "crosscut": "funnel_data_quality",
}
CONFIDENCE = {"low", "medium", "high"}


def validate_contract(c: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    stage = c.get("stage")
    if stage not in ALLOWED_STAGES:
        errors.append("stage must be one of " + ", ".join(sorted(ALLOWED_STAGES)))
    metric = c.get("metric")
    if not isinstance(metric, str) or not metric:
        errors.append("metric is required")
    if c.get("confidence") not in CONFIDENCE:
        errors.append("confidence must be low/medium/high")
    due = c.get("due")
    if due:
        try:
            date.fromisoformat(str(due))
        except Exception:  # noqa: BLE001
            errors.append("due must be YYYY-MM-DD")
    return not errors, errors


def investigation_contract(stage: str, reasons: list[str], risk: dict | None = None,
                           diagnostics: dict | None = None, owner: str | None = None) -> dict:
    risk = risk or {}
    diagnostics = diagnostics or {}
    evidence: list[str] = []
    for why in reasons:
        evidence.append(why)
    if risk.get("value_at_risk_label"):
        evidence.append(f"Estimated value at risk: {risk['value_at_risk_label']}")
    for row in diagnostics.get("highlights", [])[:3]:
        evidence.append(str(row))
    contract = {
        "contract_version": 1,
        "kind": "watchtower_investigation",
        "stage": stage,
        "metric": STAGE_METRIC.get(stage, f"{stage}_metric"),
        "target_lift_pp": None,
        "expected_value_vnd": risk.get("value_at_risk_vnd"),
        "owner": owner or risk.get("owner"),
        "due": (date.today() + timedelta(days=7)).isoformat(),
        "confidence": risk.get("confidence") or "medium",
        "evidence": evidence,
        "diagnostic_template": diagnostics.get("template"),
        "success_check": "Compare metric before/after completion against this contract.",
    }
    ok, errors = validate_contract(contract)
    contract["valid"] = ok
    contract["validation_errors"] = errors
    return contract


def create_contract_from_fields(fields: dict, expected_value_vnd: int | None = None) -> dict:
    stage = (fields.get("stage") or "crosscut").lower()
    contract = {
        "contract_version": 1,
        "kind": "manual_initiative",
        "stage": stage if stage in ALLOWED_STAGES else "crosscut",
        "metric": STAGE_METRIC.get(stage, "funnel_data_quality"),
        "target_lift_pp": fields.get("target_lift_pp"),
        "expected_value_vnd": expected_value_vnd,
        "owner": fields.get("owner"),
        "due": fields.get("due"),
        "confidence": fields.get("confidence") or "low",
        "evidence": fields.get("evidence") or ["User-created initiative; impact to be confirmed."],
        "success_check": "Define expected lift before work starts, then compare actual metric after completion.",
    }
    ok, errors = validate_contract(contract)
    contract["valid"] = ok
    contract["validation_errors"] = errors
    return contract


def render_contract_md(contract: dict) -> str:
    evidence = contract.get("evidence") or []
    ev = "\n".join(f"- {e}" for e in evidence) if evidence else "- None"
    lines = [
        "## Funnel Agent initiative contract",
        f"- Kind: {contract.get('kind')}",
        f"- Stage: {contract.get('stage')}",
        f"- Metric: {contract.get('metric')}",
        f"- Owner: {contract.get('owner') or 'TBD'}",
        f"- Due: {contract.get('due') or 'TBD'}",
        f"- Expected value at risk / upside: {contract.get('expected_value_vnd') or 'TBD'} VND",
        f"- Target lift: {contract.get('target_lift_pp') if contract.get('target_lift_pp') is not None else 'TBD'} pp",
        f"- Confidence: {contract.get('confidence')}",
        "\n### Evidence",
        ev,
        "\n### Success check",
        contract.get("success_check") or "Compare before/after metric movement.",
    ]
    if not contract.get("valid", True):
        lines += ["\n### Validation gaps"] + [f"- {e}" for e in contract.get("validation_errors", [])]
    return "\n".join(lines)

# Compatibility helpers for earlier main.py revisions.
def infer_stage(text: str | None) -> str | None:
    msg = (text or "").lower()
    if any(k in msg for k in ["traffic", "eligible", "acquisition", "entry"]):
        return "traffic"
    if any(k in msg for k in ["submit", "submission", "docs", "document", "kyc", "form"]):
        return "submission"
    if any(k in msg for k in ["approval", "approve", "review", "risk", "income"]):
        return "approval"
    if any(k in msg for k in ["completion", "complete", "completed", "payout", "e-sign", "esign", "disbursement"]):
        return "completion"
    if any(k in msg for k in ["data", "platform", "schema", "logging", "monitor"]):
        return "crosscut"
    return None


def validate_create_fields(fields: dict, original_message: str = "") -> dict:
    out = dict(fields or {})
    out["summary"] = str(out.get("summary") or original_message or "New initiative").strip()
    stage = (out.get("stage") or infer_stage(original_message) or "").lower().strip()
    out["stage"] = stage if stage in ALLOWED_STAGES else None
    out["owner"] = out.get("owner") or None
    out["due"] = out.get("due") or None
    if out.get("confidence") not in CONFIDENCE:
        out["confidence"] = "low"
    ev = out.get("evidence")
    if not isinstance(ev, list) or not ev:
        out["evidence"] = [original_message] if original_message else ["User-created initiative"]
    return out


def contract_markdown(contract: dict, title: str = "Funnel Agent initiative contract") -> str:
    c = dict(contract or {})
    if "kind" not in c:
        c = create_contract_from_fields(c)
    text = render_contract_md(c)
    if title and not text.startswith("## " + title):
        text = text.replace("## Funnel Agent initiative contract", "## " + title, 1)
    return text
