"""Deterministic business-impact ranking for Funnel Watchtower.

This is the defensibility layer: target gaps are translated into estimated value
at risk, then adjusted with execution risk from Jira. The LLM can explain these
facts, but never calculates or invents them.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

import funnel_metrics as fm

STAGE_ORDER = ["submission", "approval", "disbursement"]
STAGE_TO_RATE = {
    "submission": "submission_rate_pct",
    "approval": "approval_rate_pct",
    "disbursement": "disbursement_rate_pct",
}
RATE_LABEL = {
    "submission_rate_pct": "Submission rate",
    "approval_rate_pct": "Approval rate",
    "disbursement_rate_pct": "Disbursement rate",
}
FORMULA_NOTE = "value_at_risk = stage volume x target gap x downstream conversion x avg ticket; execution risk adjusts the ranking score."


def _fmt_vnd(v: float | int | None) -> str:
    if v is None:
        return "n/a"
    v = float(v)
    if v >= 1e9:
        return f"{v / 1e9:.2f}B VND"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M VND"
    return f"{v:,.0f} VND"


def fmt_vnd(v: float | int | None) -> str:
    return _fmt_vnd(v)


def _is_done(i: dict) -> bool:
    return str(i.get("status") or "").lower() == "done"


def _is_blocked(i: dict) -> bool:
    labels = [str(l).lower() for l in i.get("labels", [])]
    return "blocked" in labels or str(i.get("status") or "").lower() == "blocked"


def _is_overdue(i: dict, today: str | None = None) -> bool:
    today = today or date.today().isoformat()
    due = i.get("due")
    return bool(due) and due < today and not _is_done(i)


def estimate_value_at_risk(stage: str, row: dict | None = None,
                           targets: dict | None = None) -> dict:
    """Estimate downstream disbursement value lost to the latest target gap.

    The formula is simple and auditable for a hackathon/demo:
    - submission: traffic * submission_gap * actual approval rate * actual disbursement rate * avg ticket
    - approval: submission * approval_gap * actual disbursement rate * avg ticket
    - disbursement: approval * disbursement_gap * avg ticket
    """
    row = row or fm.rows()[-1]
    targets = targets or fm.targets()
    rate_key = STAGE_TO_RATE.get(stage)
    if not rate_key:
        return {"stage": stage, "metric_key": None, "value_at_risk_vnd": 0, "missed_disbursements": 0, "formula": "unsupported stage"}

    actual = row.get(rate_key)
    target = targets.get(rate_key)
    gap_pp_positive = max(0.0, round((target or 0) - (actual or 0), 1)) if actual is not None and target is not None else 0.0
    gap = gap_pp_positive / 100.0
    avg_ticket = row.get("avg_ticket_vnd") or 0
    approval_rate = (row.get("approval_rate_pct") or 0) / 100.0
    disbursement_rate = (row.get("disbursement_rate_pct") or 0) / 100.0

    if stage == "submission":
        missed_disbursements = (row.get("traffic") or 0) * gap * approval_rate * disbursement_rate
        formula = "traffic x submission gap x actual approval rate x actual disbursement rate x avg ticket"
    elif stage == "approval":
        missed_disbursements = (row.get("submission") or 0) * gap * disbursement_rate
        formula = "submission volume x approval gap x actual disbursement rate x avg ticket"
    elif stage == "disbursement":
        missed_disbursements = (row.get("approval") or 0) * gap
        formula = "approval volume x disbursement gap x avg ticket"
    else:
        missed_disbursements = 0
        formula = "unsupported stage"

    value = round(missed_disbursements * avg_ticket)
    return {
        "stage": stage,
        "metric_key": rate_key,
        "metric": RATE_LABEL.get(rate_key, rate_key),
        "actual_pct": actual,
        "target_pct": target,
        "gap_pp": round(-gap_pp_positive, 1) if gap_pp_positive else 0.0,
        "target_gap_pp": gap_pp_positive,
        "positive_gap_pp": gap_pp_positive,
        "missed_disbursements": round(missed_disbursements, 1),
        "avg_ticket_vnd": avg_ticket,
        "value_at_risk_vnd": value,
        "estimated_value_at_risk_vnd": value,
        "value_at_risk_label": _fmt_vnd(value),
        "value_at_risk_display": _fmt_vnd(value),
        "formula": formula,
    }


def _owner_for_stage(stage: str, issues: Iterable[dict], owners: dict | None = None) -> str | None:
    if owners and owners.get(stage):
        return owners[stage]
    counts: dict[str, int] = {}
    for issue in issues:
        if issue.get("stage") == stage:
            who = issue.get("owner") or issue.get("assignee") or "Unassigned"
            counts[who] = counts.get(who, 0) + 1
    return max(counts, key=counts.get) if counts else None


def execution_risk(stage: str, issues: list[dict] | None = None) -> dict:
    stage_issues = [i for i in (issues or []) if i.get("stage") == stage and not _is_done(i)]
    blocked = [i for i in stage_issues if _is_blocked(i)]
    overdue = [i for i in stage_issues if _is_overdue(i)]
    in_progress = [i for i in stage_issues if str(i.get("status") or "").lower() == "in progress"]
    score = min(5, len(blocked) * 2 + len(overdue) * 2 + max(0, len(stage_issues) - 4))
    reasons: list[str] = []
    if blocked:
        reasons.append(f"{len(blocked)} blocked")
    if overdue:
        reasons.append(f"{len(overdue)} overdue")
    if len(stage_issues) > 4:
        reasons.append(f"{len(stage_issues)} open items")
    if not reasons:
        reasons.append("no blocked/overdue work detected")
    return {
        "score": score,
        "open_count": len(stage_issues),
        "in_progress_count": len(in_progress),
        "blocked_count": len(blocked),
        "overdue_count": len(overdue),
        "blocked": blocked,
        "overdue": overdue,
        "reasons": reasons,
    }


def _recommend(stage: str, owner: str | None, var: dict, exec_risk: dict) -> str:
    who = f" with {owner}" if owner else ""
    if exec_risk["blocked"] or exec_risk["overdue"]:
        return f"Escalate {stage} recovery{who}; unblock/refresh the overdue initiative and open one investigation if none exists."
    if var.get("value_at_risk_vnd"):
        return f"Open/update a {stage} investigation{who} with diagnostic evidence and an expected lift contract."
    return f"Monitor {stage}; no material value-at-risk estimate from current targets."


def _signals(item: dict) -> list[str]:
    reasons: list[str] = []
    miss = item.get("target_miss") or {}
    anomaly = item.get("anomaly") or {}
    if miss:
        reasons.append(f"{miss.get('metric')} {miss.get('actual_pct')}% vs {miss.get('target_pct')}% target ({miss.get('gap_pp')}pp)")
    elif item.get("target_pct") is not None:
        reasons.append(f"{item.get('metric')} {item.get('actual_pct')}% vs {item.get('target_pct')}% target ({item.get('gap_pp')}pp)")
    if anomaly:
        reasons.append(f"{anomaly.get('metric')} fell {abs(anomaly.get('delta_pp') or 0)}pp MoM ({anomaly.get('prev_pct')}% to {anomaly.get('latest_pct')}%)")
    return reasons


def rank_stage_problems(open_issues: list[dict] | None = None,
                        owners: dict | None = None) -> list[dict]:
    """Rank problematic stages by value at risk, trend severity and execution risk."""
    summary = fm.summary()
    latest = summary["latest"]
    targets = summary.get("targets", {})
    anomalies_by_stage = {a["stage"]: a for a in summary.get("anomalies", [])}
    misses_by_stage = {m["stage"]: m for m in summary.get("target_misses", [])}
    stages = set(anomalies_by_stage) | set(misses_by_stage)
    ranked: list[dict] = []

    for stage in sorted(stages, key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 99):
        var = estimate_value_at_risk(stage, latest, targets)
        exec_risk = execution_risk(stage, open_issues)
        anomaly = anomalies_by_stage.get(stage)
        miss = misses_by_stage.get(stage)
        trend_weight = 1.25 if anomaly else 1.0
        execution_weight = 1.0 + (exec_risk["score"] * 0.08)
        score = round((var["value_at_risk_vnd"] / 1_000_000) * trend_weight * execution_weight, 1)
        owner = _owner_for_stage(stage, open_issues or [], owners)
        item = {
            **var,
            "month": summary.get("latest_month"),
            "mom_delta_pp": anomaly.get("delta_pp") if anomaly else None,
            "anomaly": anomaly,
            "target_miss": miss,
            "owner": owner,
            "execution_risk": exec_risk,
            "impact_score": score,
            "score": score,
            "confidence": "medium" if var["value_at_risk_vnd"] else "low",
            "recommended_action": _recommend(stage, owner, var, exec_risk),
        }
        item["reasons"] = _signals(item)
        ranked.append(item)

    ranked.sort(key=lambda x: (x["impact_score"], x["value_at_risk_vnd"]), reverse=True)
    for idx, item in enumerate(ranked, 1):
        item["rank"] = idx
    return ranked


def render_markdown(ranked: list[dict] | None = None) -> str:
    ranked = ranked if ranked is not None else rank_stage_problems()
    if not ranked:
        return "No target miss or significant MoM drop is currently ranked."
    rows = [
        "| Rank | Stage | Signal | Value at risk | Owner | Execution risk | Recommended action |",
        "|---:|---|---|---:|---|---|---|",
    ]
    for r in ranked:
        signals = []
        if r.get("gap_pp"):
            signals.append(f"{r['actual_pct']}% vs {r['target_pct']}% target ({r['gap_pp']}pp)")
        if r.get("mom_delta_pp") is not None:
            signals.append(f"MoM {r['mom_delta_pp']}pp")
        er = ", ".join((r.get("execution_risk") or {}).get("reasons", []))
        rows.append("| {rank} | {stage} | {signal} | {var} | {owner} | {er} | {rec} |".format(
            rank=r.get("rank"), stage=str(r.get("stage", "")).title(), signal="; ".join(signals) or r.get("metric"),
            var=r.get("value_at_risk_display") or r.get("value_at_risk_label") or _fmt_vnd(r.get("value_at_risk_vnd")),
            owner=r.get("owner") or "Unassigned", er=er,
            rec=str(r.get("recommended_action") or "").replace("|", "/"),
        ))
    return "\n".join(rows)


def render_ranking(pack: dict | list[dict] | None = None) -> str:
    if isinstance(pack, dict):
        ranked = pack.get("ranking") or pack.get("ranked_stage_problems") or []
    else:
        ranked = pack
    return render_markdown(ranked)


def top_risk_sentence(ranked: list[dict] | None = None) -> str:
    ranked = ranked if ranked is not None else rank_stage_problems()
    if not ranked:
        return "No stage is currently below target or showing a significant MoM drop."
    r = ranked[0]
    return (f"Top business risk: {r['stage'].title()} - {r['value_at_risk_display']} estimated at risk, "
            f"owner {r.get('owner') or 'Unassigned'}, {', '.join(r['execution_risk']['reasons'])}.")


def summary(open_issues: list[dict] | None = None, owners: dict | None = None) -> dict:
    ranked = rank_stage_problems(open_issues, owners)
    return {
        "latest_month": fm.summary().get("latest_month"),
        "ranked_stage_problems": ranked,
        "top_problem": ranked[0] if ranked else None,
        "ranking_markdown": render_markdown(ranked),
        "formula_note": FORMULA_NOTE,
    }


def rank_stage_risks(open_issues: list[dict] | None = None, owners: dict | None = None) -> dict:
    ranked = rank_stage_problems(open_issues=open_issues, owners=owners)
    return {
        "ranking": ranked,
        "top": ranked[0] if ranked else None,
        "top_problem": ranked[0] if ranked else None,
        "markdown": render_markdown(ranked),
        "formula_note": FORMULA_NOTE,
    }


def investigation_contract(stage: str, reasons: list[str], owner: str | None = None,
                           risk: dict | None = None, diagnostics: dict | None = None) -> dict:
    import contracts as ct
    risk = dict(risk or {})
    if "value_at_risk_vnd" not in risk and "estimated_value_at_risk_vnd" in risk:
        risk["value_at_risk_vnd"] = risk.get("estimated_value_at_risk_vnd")
    if "value_at_risk_label" not in risk:
        risk["value_at_risk_label"] = risk.get("value_at_risk_display") or _fmt_vnd(risk.get("value_at_risk_vnd"))
    diag = dict(diagnostics or {})
    if "highlights" not in diag and diag.get("top_findings"):
        diag["highlights"] = diag.get("top_findings")
    return ct.investigation_contract(stage, reasons, risk, diag, owner=owner)
