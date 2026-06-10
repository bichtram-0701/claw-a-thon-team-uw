"""
Turn verified funnel metrics into a written report.

Primary path: send the metrics brief to the MaaS LLM (Gemma/Qwen) for an
executive narrative + recommendations. Fallback path: if no LLM is configured or
the call fails, build a deterministic template report so the demo always works.
Both paths emit the same metric tables; only the prose differs.
"""
from __future__ import annotations

from .llm_client import LLMClient
from .prompts import AI_DISCLOSURE, SYSTEM_PROMPT, build_user_prompt


def _metrics_tables(analysis: dict) -> str:
    f = analysis["funnel"]
    L = [f"## {f['funnel_name']} — metrics", "",
         f"Records analyzed: **{analysis['records']:,}**  |  "
         f"Overall conversion: **{f['overall_conversion_pct']}%**", "",
         "| Stage | Count | % of top | Step conv. | Drop-off |",
         "|---|---:|---:|---:|---:|"]
    for s in f["steps"]:
        conv = "—" if s["step_conversion_pct"] is None else f"{s['step_conversion_pct']}%"
        drop = "—" if s["step_dropoff_pct"] is None else f"{s['step_dropoff_pct']}%"
        L.append(f"| {s['stage']} | {s['count']:,} | {s['pct_of_top']}% | {conv} | {drop} |")
    L += ["", "### Stage velocity (hours)",
          "| Transition | Median | p90 | n |", "|---|---:|---:|---:|"]
    for k, v in analysis["timing"].items():
        L.append(f"| {k} | {v['median_hours']} | {v['p90_hours']} | {v['n']:,} |")
    for dim, table in analysis["segments"].items():
        L += ["", f"### By {dim}",
              f"| {dim} | Top | Bottom | Overall conv. |", "|---|---:|---:|---:|"]
        for r in table:
            L.append(f"| {r['value']} | {r['top']:,} | {r['bottom']:,} | "
                     f"{r['overall_conversion_pct']}% |")
    return "\n".join(L)


def _fallback_narrative(analysis: dict) -> str:
    f = analysis["funnel"]
    # pick best/worst segment from the first available dimension
    seg_line = ""
    for dim, table in analysis["segments"].items():
        ranked = sorted(table, key=lambda r: r["overall_conversion_pct"])
        if len(ranked) >= 2:
            lo, hi = ranked[0], ranked[-1]
            seg_line = (f"By {dim}, **{hi['value']}** converts best "
                        f"({hi['overall_conversion_pct']}%) and **{lo['value']}** "
                        f"worst ({lo['overall_conversion_pct']}%).")
            break
    slowest = max(analysis["timing"].items(),
                  key=lambda kv: kv[1]["median_hours"], default=(None, None))
    slow_txt = (f"The slowest transition is **{slowest[0]}** "
                f"(median {slowest[1]['median_hours']}h)." if slowest[0] else "")
    return (
        "## Analysis\n\n"
        f"Overall conversion from {f['steps'][0]['stage']} to "
        f"{f['steps'][-1]['stage']} is **{f['overall_conversion_pct']}%**. "
        f"The biggest leak by volume is **{f['biggest_leak_by_volume']}** "
        f"(~{f['biggest_leak_count']:,} lost), while the worst step by rate is "
        f"**{f['worst_conversion_step']}** "
        f"({f['worst_conversion_dropoff_pct']}% drop). {seg_line} {slow_txt}\n\n"
        "## Recommendations\n\n"
        f"1. Attack the largest pool first: **{f['biggest_leak_by_volume']}** is "
        f"where the most users are lost — reducing this drop has the highest "
        f"absolute upside.\n"
        f"2. Investigate **{f['worst_conversion_step']}**, the steepest single-step "
        f"drop, for friction or qualification issues.\n"
        "3. Lift weak segments toward the average — they are existing volume, not "
        "new acquisition.\n\n"
        "_(Deterministic fallback report: no LLM was configured. Set LLM_API_KEY "
        "to get the full AI-written narrative.)_"
    )


def synthesize_report(analysis: dict, client: LLMClient | None = None) -> dict:
    client = client or LLMClient()
    used_llm = False
    note = ""
    if client.available:
        try:
            narrative = client.chat(SYSTEM_PROMPT, build_user_prompt(analysis))
            used_llm = True
        except Exception as e:  # noqa: BLE001 — degrade gracefully for demos
            narrative = _fallback_narrative(analysis)
            note = f"\n\n> ⚠️ LLM call failed ({e}); used deterministic fallback."
    else:
        narrative = _fallback_narrative(analysis)

    report = "\n\n".join([
        AI_DISCLOSURE,
        f"# Conversion Funnel Report — {analysis['funnel']['funnel_name']}",
        narrative + note,
        "---",
        _metrics_tables(analysis),
    ])
    return {"report_markdown": report, "used_llm": used_llm,
            "model": client.model if used_llm else None}
