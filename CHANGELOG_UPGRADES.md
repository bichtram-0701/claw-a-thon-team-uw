# Upgrade changelog

## v17 demo package

- Renamed the user-facing bot to **Funnel Agent**.
- Default MaaS model is now `openai/gpt-oss-20b`; `/model` reports the configured model from runtime config instead of asking the LLM to self-identify.
- User-facing final-stage wording is **Disbursement**: `Disbursement (4)`, `Disbursement Volume`, and `Disbursement rate (4)/(3)`.
- `/metrics` is the main read-only command for both KPI readouts and safe data drilldowns; `/query` remains as an optional advanced alias.
- Added monthly Jira and Confluence seed evidence for March, April, and May so historical questions can cite prior work and decisions.
- Added `DEMO_VIDEO_STORYBOARD.md` to show the full workflow across chat, Jira, Confluence, and Teams.
- Added Teams workflow framing: new-task card, task-update card, 09:00 overdue/stale digest, 17:00 due-tomorrow reminder, and off-track blocker posting.
- Cleaned legacy/outdated files from the package: old portfolio specs, pivot docs, legacy agent folder, old loan CSV, caches, and local secrets.

## Execution-intelligence upgrade

- Added `impact.py` for deterministic value-at-risk and execution-risk ranking.
- Added validated `router.py` with slash-command routing, semantic fallback, clarification behavior, and write guards.
- Added `contracts.py` validation helpers for initiative and investigation contracts.
- Updated `main.py` so metrics answers show the top recovery priority and `/jira flag it` uses impact ranking and Jira idempotency.
- Updated `sql_analyst.py` to use safe templates before LLM SQL fallback.
- Updated `jira_client.py` with comments, richer descriptions, stage ownership, blocker context, and open-investigation lookup.
- Updated `confluence_client.py` with recent-page search and weekly page upsert.
- Updated `briefing.py` with weekly meeting packs and renderers.
- Added `weekly.py` wrapper for weekly summary workflows.

## Data consistency fix

- Regenerated `data/funnel_synthetic.csv` as a downscaled row-level fixture for the six demo months.
- `funnel_metrics.py` aggregates monthly metrics from the CSV when present, so daily SQL totals and monthly funnel totals use one source of truth.
- `sql_analyst.py` treats `day over day` as a daily-volume template and makes `break May down by drop reason` explain the Submission -> Approval loss instead of mixing successful disbursements with drops.
- Added offline regression checks for May reconciliation: Traffic 800 -> Submission 216 -> Approval 24 -> Disbursement 23, with 192 Submission -> Approval drop rows.

## Test status

Offline suite: `160 passed, 0 failed`.

The offline suite intentionally avoids live MaaS and Atlassian calls. Before a live demo, verify deployed LLM routing, Jira writes, Confluence page publishing, and any Teams webhook with synthetic credentials.

## Security packaging

The final ZIP excludes `.env`, `.git`, caches, pyc files, local runtime state, and legacy prototype folders. Use `.env.example` as the only shared credential template.
