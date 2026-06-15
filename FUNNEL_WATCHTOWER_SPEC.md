# Funnel Watchtower - Agent Spec

## Product thesis

Funnel Watchtower is a closed-loop execution intelligence system for owned funnel metrics. It detects target drift, estimates value at risk, links the problem to Jira ownership, creates or updates accountable recovery work, and prepares weekly operating summaries in Confluence.

## Primary user

A business, product, marketing, operations, or risk lead responsible for a recurring funnel such as:

```text
Traffic -> Submission -> Approval -> Final outcome
```

The current synthetic demo labels the final outcome as `Completion`, but the workflow is intentionally domain-agnostic.

## What the agent must do

1. Answer funnel metric questions from deterministic data.
2. Rank stage problems by value at risk and Jira execution risk.
3. Diagnose drops with safe SQL templates and contribution-style slices.
4. Show who owns each stage and what work is blocked, overdue, or due soon.
5. Create, assign, or update Jira issues with structured initiative contracts.
6. Avoid duplicate investigations by searching for existing stage/metric/month work.
7. Summarize Confluence decisions and recent pages.
8. Draft or publish a weekly meeting brief to Confluence.
9. Produce bilingual manager-friendly answers without inventing facts.

## LLM role

The LLM is a replaceable language layer used for:

- slash-command routing with semantic fallback
- bounded JSON extraction
- concise narration from verified JSON
- optional fallback SQL generation when no deterministic template matches

The LLM must not be trusted to compute:

- conversion metrics
- target gaps
- value at risk
- issue ownership
- Jira write eligibility
- duplicate-ticket detection
- SQL safety

## Core modules

| Module | Responsibility |
|---|---|
| `router.py` | Slash-command routing (`/metrics`, `/query`, `/jira`, `/confluence`, `/teams`, `/help`) with semantic fallback, warnings, clarification, and write-command guards |
| `funnel_metrics.py` | Monthly funnel metrics, anomalies, target misses |
| `impact.py` | Value-at-risk and execution-risk ranking |
| `sql_analyst.py` | Template-first safe SQL analytics and diagnostics |
| `contracts.py` | Initiative contract validation and rendering |
| `jira_client.py` | Jira reads/writes, assignee resolution, investigation idempotency |
| `confluence_client.py` | Confluence search and weekly page publishing |
| `briefing.py` | Manager digest, sprint pulse, weekly meeting packet |
| `report.py` | LLM connection, JSON parsing, narration helpers |
| `weekly.py` | Thin weekly-meeting workflow wrapper |

## Key safety rules

- Demo writes are enabled with `ALLOW_WRITES=true`; set `ALLOW_WRITES=false` for read-only mode.
- Assignments require a real Jira account when available; otherwise the owner label is stamped.
- `flag` creates at most one open investigation per stage/metric/month.
- SQL must be read-only and pass validation.
- Model JSON is schema-validated before use.
- Numeric estimates are generated only by deterministic code.

## Defensibility

Generic assistants can search Jira or Confluence. Watchtower is defensible because it encodes the team's operating graph:

```text
metric -> stage -> target -> owner -> initiative -> blocker -> decision -> outcome
```

The moat is not the chatbot. The moat is the funnel execution graph, value-at-risk scoring, Jira idempotency, structured initiative contracts, and the weekly management loop.
