# Funnel Agent spec

## Product thesis

Funnel Agent is a closed-loop execution intelligence system for owned funnel metrics. It detects target drift, estimates value at risk, links the problem to Jira ownership, creates or updates accountable recovery work, prepares weekly operating summaries in Confluence, and pushes blockers to Teams.

## Primary user

A business, product, marketing, operations, or risk lead responsible for a recurring funnel such as:

```text
Traffic -> Submission -> Approval -> Disbursement
```

The current synthetic demo labels the final outcome as `Disbursement`. In another business, the final stage could be purchase, activation, merchant live, contract signed, or request completed.

## What the agent must do

1. Answer funnel metric questions from deterministic data.
2. Rank stage problems by value at risk and Jira execution risk.
3. Diagnose drops with safe SQL templates and contribution-style slices.
4. Show who owns each stage and what work is blocked, overdue, due soon, or stale.
5. Create, assign, or update Jira issues with structured initiative contracts.
6. Avoid duplicate investigations by searching for existing stage/metric/month work.
7. Summarize Confluence decisions and recent pages.
8. Draft or publish a weekly meeting brief to Confluence.
9. Post Teams notifications for new tasks, updates, overdue/stale digests, due-tomorrow reminders, and off-track blockers.
10. Return runtime/model info via `/model` without asking the LLM to self-identify.

## LLM role

The LLM is a replaceable language layer used for semantic fallback, bounded JSON extraction, and concise narration from verified data.

The LLM must not be trusted to compute conversion metrics, target gaps, value at risk, issue ownership, Jira write eligibility, duplicate-ticket detection, SQL safety, or Teams/Confluence write behavior.

## Core modules

| Module | Responsibility |
|---|---|
| `router.py` | Slash-command routing (`/funnel`, `/jira`, `/confluence`, `/teams`, `/help`, `/model`; `/query` remains an alias) with semantic fallback, warnings, clarification, and write-command guards |
| `funnel_metrics.py` | Monthly funnel metrics, anomalies, target misses |
| `impact.py` | Value-at-risk and execution-risk ranking |
| `sql_analyst.py` | Template-first safe SQL analytics and diagnostics |
| `contracts.py` | Initiative contract validation and rendering |
| `jira_client.py` | Jira reads/writes, assignee resolution, investigation idempotency |
| `confluence_client.py` | Confluence search and weekly page publishing |
| `teams_client.py` | Teams Adaptive Cards for issue events and digests |
| `briefing.py` | Manager digest, sprint pulse, weekly meeting packet |
| `report.py` | LLM connection, JSON parsing, narration helpers |

## Defensibility

Generic assistants can search Jira or Confluence. Funnel Agent is defensible because it encodes the team's operating graph:

```text
metric -> stage -> target -> owner -> initiative -> blocker -> decision -> outcome
```

The long-term moat is the execution graph, value-at-risk scoring, idempotent Jira work, structured initiative contracts, Teams notification loop, and future closed-loop outcome learning.
