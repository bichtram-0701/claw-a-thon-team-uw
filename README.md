# Lending Portfolio Watchdog

> Claw-a-thon 2026 — **Team UW** — Track: **Data Analysis**

AI agent on GreenNode AgentBase that answers loan-portfolio questions in plain
language, automatically flags accounts about to roll into NPL, and writes
manager-ready portfolio reports — turning hours of manual analysis into minutes.

## Problem

Lending teams track portfolio health manually: exporting data, rebuilding the same
overdue/NPL pivot tables every week, and eyeballing for risky accounts. Segment
deterioration is often spotted weeks late, after accounts have already rolled into NPL.

## User

Portfolio / credit risk analysts and lending team leads who need daily visibility
without manual report building.

## Solution

Ask in plain language (Vietnamese or English) — the agent:

1. **Q&A** — "How is the portfolio doing?", "Which segment has rising risk?", "Compare provinces"
2. **Watchdog** — auto-flags accounts within 6 days of the 90-DPD NPL cliff
3. **Reports** — full markdown report: NPL ratio, DPD buckets, concentration,
   period-over-period trend, written by MaaS LLM (Qwen/Gemma) with a deterministic
   fallback so the agent never breaks

## Value

Hours of manual reporting → minutes; deterioration spotted before NPL, not after;
consistent metrics and narrative every time.

## Try it (live)

Deployed endpoint: https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn

```bash
curl -X POST https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/invocations -H 'Content-Type: application/json' \
  -d '{"message": "which accounts are at risk?"}'

curl -X POST https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/invocations -H 'Content-Type: application/json' \
  -d '{"message": "cho tôi báo cáo tuần", "language": "vi"}'
```

Run locally: `pip install -r requirements.txt && python main.py` (port 8080).

## Demo video

🎬 _[link — to be added]_

## Architecture & design

See [AGENT_SPEC.md](AGENT_SPEC.md). Key choice: a data-adapter layer — the agent
never knows where data comes from; swapping the synthetic CSV for a real source
post-competition requires no change to agent logic.

## Models & resources

- GreenNode MaaS (competition tokens): Qwen-3-27B / gemma-4-31b-it, auto-selected at deploy
- Deploy pipeline: GitHub Actions → AgentBase Container Registry → Agent Runtime
  (endpoints from the BTC's [greennode-agentbase-skills](https://github.com/vngcloud/greennode-agentbase-skills) pack)
- No external paid models used

## Data

100% synthetic (seeded generator, no PII, no real customers). Cite: "Claw-a-thon 2026".

## Team

| Member | Department |
|--------|-----------|
| Hathy (Tramctb2) | Credit Risk |
| Rino (rinotrann) | _[dept]_ |
