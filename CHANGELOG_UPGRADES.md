# Upgrade changelog

## Execution-intelligence upgrade

- Added `impact.py` for deterministic value-at-risk and execution-risk ranking.
- Added LLM-first but validated `router.py`; keywords are now fallback only.
- Added `contracts.py` validation helpers for initiative and investigation
  contracts.
- Updated `main.py` so metrics answers show the top recovery priority and `flag it`
  uses impact ranking and Jira idempotency.
- Updated `sql_analyst.py` to use safe templates before LLM SQL fallback.
- Updated `jira_client.py` with comments, richer descriptions, extra labels, and
  open-investigation lookup.
- Updated `confluence_client.py` with recent-page search and weekly page upsert.
- Updated `briefing.py` with weekly meeting packs and renderers.
- Added `weekly.py` wrapper for weekly summary workflows.
- Excluded legacy portfolio/conversion prototypes from the clean submission package.
- Updated README, pitch, submission draft, and evaluation prompts.

## Test status

Offline suite: `78 passed, 0 failed`.

The offline suite intentionally avoids live MaaS and Atlassian calls. Before a live
demo, verify deployed LLM routing, Jira writes, Confluence page publishing, and any
Teams webhook with synthetic credentials.

## Security packaging

The final ZIP should exclude `.env`, `.git`, caches, pyc files, and local runtime
state. Use `.env.example` as the only shared credential template.
