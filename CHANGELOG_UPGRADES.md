# Upgrade changelog

## Execution-intelligence upgrade

- Added `impact.py` for deterministic value-at-risk and execution-risk ranking.
- Added LLM-first but validated `router.py`; keywords are now fallback only.
- Added `contracts.py` validation helpers for initiative and investigation
  contracts.
- Updated `main.py` so metrics answers show the top recovery priority and `jira: flag it`
  uses impact ranking and Jira idempotency.
- Updated `sql_analyst.py` to use safe templates before LLM SQL fallback.
- Updated `jira_client.py` with comments, richer descriptions, extra labels, and
  open-investigation lookup.
- Updated `confluence_client.py` with recent-page search and weekly page upsert.
- Updated `briefing.py` with weekly meeting packs and renderers.
- Added `weekly.py` wrapper for weekly summary workflows.
- Excluded legacy portfolio/conversion prototypes from the clean submission package.
- Updated README, pitch, submission draft, and evaluation prompts.


## Data consistency fix

- Regenerated `data/funnel_synthetic.csv` as a downscaled row-level fixture for the six demo months (hundreds of rows per month).
- `funnel_metrics.py` now aggregates monthly metrics from the CSV when present, so daily SQL totals and monthly funnel totals use one source of truth.
- `sql_analyst.py` now treats `day over day` as a daily-volume template and makes `break May down by drop reason` explain the Submission -> Approval loss instead of mixing successful completions with drops.
- Added offline regression checks for May reconciliation: Traffic 800 -> Submission 216 -> Approval 24 -> Completion 23, with 192 Submission -> Approval drop rows.

## Test status

Offline suite: `87 passed, 0 failed`.

The offline suite intentionally avoids live MaaS and Atlassian calls. Before a live
demo, verify deployed LLM routing, Jira writes, Confluence page publishing, and any
Teams webhook with synthetic credentials.

## Security packaging

The final ZIP should exclude `.env`, `.git`, caches, pyc files, and local runtime
state. Use `.env.example` as the only shared credential template.
