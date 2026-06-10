"""Prompts and the mandatory AI-disclosure string (Rulebook §11.1)."""

# Rulebook §11.1: "Every agent must clearly declare to end users that end users
# are interacting with artificial intelligence (AI)."
AI_DISCLOSURE = (
    "> 🤖 **AI-generated.** This report was produced by an automated AI agent "
    "(Conversion Funnel Analyst, GreenNode Claw-a-thon 2026). The numbers are "
    "computed deterministically from your data; the written analysis is generated "
    "by a large language model and should be reviewed before acting on it."
)

SYSTEM_PROMPT = (
    "You are the Conversion Funnel Analyst, a data-analysis AI agent. You are "
    "given VERIFIED, pre-computed funnel metrics (counts, step conversion, "
    "drop-off, stage velocity, and segment breakdowns). Your job is to write a "
    "concise, decision-ready report.\n\n"
    "Hard rules:\n"
    "- Use ONLY the numbers provided. Never invent or alter a figure.\n"
    "- Quantify every claim with a number from the data.\n"
    "- Be concise; no filler, no apologies.\n"
    "- The biggest leak by VOLUME and the worst step by RATE may differ — address both.\n\n"
    "Produce these sections in order:\n"
    "1. Executive summary (3-4 sentences): overall conversion, the single biggest "
    "leak with the volume lost, and the most actionable segment finding.\n"
    "2. Stage-by-stage read: walk the funnel, noting where and how much is lost, "
    "and call out the slowest step from the velocity data.\n"
    "3. Segment insight: name the strongest and weakest segments with their numbers.\n"
    "4. Recommendations: 3-5 prioritised actions, each tied to a specific number "
    "and ranked by estimated impact (addressable population x plausible lift)."
)


def build_user_prompt(analysis: dict) -> str:
    """Render the verified metrics into a compact, model-friendly brief."""
    f = analysis["funnel"]
    lines = [f"FUNNEL: {f['funnel_name']}",
             f"Records analyzed: {analysis['records']:,}",
             f"Overall conversion (top -> bottom): {f['overall_conversion_pct']}%",
             f"Biggest leak by volume: {f['biggest_leak_by_volume']} "
             f"({f['biggest_leak_count']:,} lost)",
             f"Worst step by rate: {f['worst_conversion_step']} "
             f"({f['worst_conversion_dropoff_pct']}% drop)",
             "", "STAGES:"]
    for s in f["steps"]:
        conv = "-" if s["step_conversion_pct"] is None else f"{s['step_conversion_pct']}%"
        drop = "-" if s["step_dropoff_pct"] is None else f"{s['step_dropoff_pct']}%"
        lines.append(f"  {s['stage']}: {s['count']:,} "
                     f"({s['pct_of_top']}% of top) | step conv {conv} | drop {drop}")
    lines.append("")
    lines.append("STAGE VELOCITY (hours):")
    for k, v in analysis["timing"].items():
        lines.append(f"  {k}: median {v['median_hours']}, p90 {v['p90_hours']} (n={v['n']:,})")
    for dim, table in analysis["segments"].items():
        lines.append("")
        lines.append(f"BY {dim.upper()} (top count, bottom count, overall conv%):")
        for r in table:
            lines.append(f"  {r['value']}: {r['top']:,} -> {r['bottom']:,} "
                         f"({r['overall_conversion_pct']}%)")
    return "\n".join(lines)
