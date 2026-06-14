# Funnel Watchtower

Claw-a-thon 2026 - Team UW - Track: Agentic Assistant

**Tagline:** Turns funnel drift into ranked, owned, auditable recovery actions.

Funnel Watchtower is a closed-loop execution intelligence agent for business funnels. It is designed for any recurring funnel owned by a team: marketing acquisition, product onboarding, merchant activation, sales pipeline, operations workflow, or a simple application funnel.

The demo uses one straightforward synthetic funnel:

`Traffic -> Submission -> Approval -> Completion`

Think of the final stage as the business outcome. In another team, that could be purchase, activation, contract signed, merchant live, request completed, or payout. The point is not the domain; the point is the recovery workflow.

Funnel Watchtower does more than summarize Jira. It detects target drift, estimates business value at risk, ranks the affected funnel stage, checks Jira ownership and execution risk, drafts or updates the recovery task, and prepares weekly meeting notes from metrics, Jira, and Confluence.

The LLM layer is deliberately bounded and replaceable. It handles semantic routing, field extraction, and manager-ready narration. Python and SQL own the facts: conversion math, target gaps, value-at-risk sizing, SQL templates, Jira issue keys, owners, write guards, and Confluence publishing.

## What changed in this upgraded version

- **LLM-first intent routing with guardrails**: fixes keyword collisions such as `daily volume` being mistaken for `standup`. Keywords remain only as fallback and validation signals.
- **Impact Ranking Engine** (`impact.py`): ranks target misses by value at risk, trend severity, and Jira execution risk.
- **Initiative contracts** (`contracts.py`): Jira issues include structured stage, metric, owner, due date, confidence, expected value, evidence, and success check.
- **Template-first SQL analyst** (`sql_analyst.py`): common breakdowns use deterministic SQL templates; LLM SQL is only fallback and still read-only validated. Daily and monthly views now reconcile from the same row-level fixture.
- **Idempotent investigations**: `flag it` searches for an existing open investigation by stage, metric, and month before creating a new Jira issue.
- **Weekly Confluence summary**: `weekly meeting summary` drafts a manager-ready weekly readout; `publish weekly meeting summary to Confluence` creates or updates a Confluence page.
- **Legacy portfolio cleanup**: the old portfolio watchdog project is excluded from this clean package so it does not mix with Watchtower runtime code.
- **Synthetic partner cleanup**: Jira seed tickets use fictional partner names only.

## Demo script

See `DEMO_PROMPTS.md` for the recommended demo prompts and exact expected outputs.

## Example questions

```text
show me the funnel metrics
what is the top business risk?
rank the target misses by value at risk
break May down by drop reason
show daily volume in May
why did approval drop?
flag the drops and assign owners to investigate
what is critical or off track right now?
who is working on what?
what did we decide about submission?
draft my standup
weekly meeting summary
publish weekly meeting summary to Confluence
```

## Core value

A dashboard can show that approval dropped. Watchtower answers the operational follow-up:

1. Which stage is the top recovery priority?
2. How much synthetic business value is at risk?
3. Who owns that stage or related work?
4. Is recovery work blocked, overdue, or missing?
5. Should we open a new investigation or update an existing one?
6. What should be discussed in the weekly meeting?

## Architecture

```text
User message
  -> router.py                 LLM-first intent classification + deterministic guards
  -> deterministic handlers
      -> funnel_metrics.py     monthly conversion, MoM anomalies, OKR target misses
      -> impact.py             value-at-risk ranking + execution-risk scoring
      -> sql_analyst.py        template-first application breakdowns
      -> jira_client.py        Jira read/create/assign/comment/search
      -> confluence_client.py  search decisions + publish weekly summaries
      -> briefing.py           manager, sprint, standup, weekly packets
      -> contracts.py          validated initiative/investigation contracts
  -> report.py                 LLM narration from verified JSON only
```

### Why the model layer is swappable

This is not a pitch about a specific model. The configured LLM is only a language layer:

| Layer | Owner |
|---|---|
| Intent understanding | LLM first, guardrail validation second |
| Funnel rates and targets | Deterministic Python |
| Value-at-risk ranking | Deterministic Python |
| Root-cause drilldown | SQL templates / contribution analysis |
| Jira write safety | Deterministic guards and idempotency |
| Ticket descriptions and summaries | LLM narration from validated JSON |
| Weekly meeting notes | Deterministic packet + LLM wording |

That makes the system cheaper, safer, reproducible, and portable across approved internal model infrastructure. If the organization changes models later, the LLM adapter can be swapped without changing the workflow logic.

## Impact ranking

Watchtower estimates value at risk with simple, auditable formulas. For example:

```text
approval value at risk = submission volume x approval target gap x actual downstream completion rate x average outcome value
```

Ranking then combines:

```text
impact_score = value_at_risk x trend_weight x execution_risk_weight
```

Execution risk comes from Jira signals such as blocked issues, overdue work, and overloaded stage work.

## Weekly Confluence summary

Ask:

```text
weekly meeting summary
```

The agent returns a weekly meeting brief with:

- executive summary
- impact-ranked risks
- Jira execution follow-up
- recent Confluence decision context
- proposed agenda

Ask:

```text
publish weekly meeting summary to Confluence
```

When `ALLOW_WRITES=true`, the agent creates or updates a Confluence page titled like:

```text
Weekly Funnel Watchtower Summary - YYYY-MM-DD
```

## Jira write safety

Writes are guarded:

- `ALLOW_WRITES=false` disables Jira and Confluence writes.
- Jira investigation creation is idempotent by stage + metric + month.
- `create` requests validate extracted fields before writing.
- Every created investigation includes an initiative contract in the Jira description.
- The agent assigns a real Jira user when possible; otherwise it stamps an owner label.

Demo default is `ALLOW_WRITES=true`. Set `ALLOW_WRITES=false` for read-only/local safety.

## Data

All data is synthetic and generated to reconcile across daily SQL and monthly metrics. See `DATA_DESIGN.md` for the full schema.


- `data/funnel_synthetic.csv`: source-of-truth row-level fixture, one distinct synthetic user/entity per row. Traffic = all rows; Submission = `stage_rank >= 2`; Approval = `stage_rank >= 3`; Completion = `stage_rank = 4`.
- `data/funnel_metrics.json`: targets, stage definitions, and fallback monthly fixture. In the normal package, `funnel_metrics.py` aggregates monthly metrics from the CSV so daily totals and monthly totals match exactly.
- `scripts/generate_synthetic_funnel.py`: deterministic generator for the row-level fixture.
- `scripts/seed_atlassian.py`: creates synthetic Jira initiatives and Confluence pages with fictional partner names.

For example, May 2026 reconciles as Traffic 800 -> Submission 216 -> Approval 24 -> Completion 23. The Submission -> Approval drop is 192 rows, and `break May down by drop reason` explains those rows instead of mixing them with successful completions.

No company systems, real customers, or real partner names are used.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Offline tests do not require network credentials or LLM access:

```bash
python tests/test_offline.py
```

Current offline suite: **87 passed, 0 failed**.

## Environment variables

See `.env.example`. Key values:

```text
LLM_API_KEY=
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
LLM_MODEL=
ATLASSIAN_SITE=
ATLASSIAN_EMAIL=
ATLASSIAN_TOKEN=
JIRA_PROJECT_KEY=UW
ALLOW_WRITES=true
CONFLUENCE_SPACE_KEY=
CONFLUENCE_SPACE_ID=
TEAMS_WEBHOOK_URL=
```

Never commit `.env`, API tokens, or personal credentials. If a token was previously shared in a ZIP or repo, rotate it.

If you renamed the Jira project/space key, set `JIRA_PROJECT_KEY` before deploying and before running the Atlassian seed workflow. The demo workspace currently uses `UW`, so all Jira reads/writes and seed scripts are scoped to `UW` by default.


## Team

| Member | Department |
|---|---|
| Hathy (Tramctb2) | Credit Risk |
| Rino (rinotrann) | TBD |


## Usage guide

For demo prompts, stage definitions, and safe defaults for ambiguous terms like `volume` and `drop`, see [`HOW_TO_USE_WATCHTOWER.md`](HOW_TO_USE_WATCHTOWER.md).

