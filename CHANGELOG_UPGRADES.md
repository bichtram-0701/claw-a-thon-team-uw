# Upgrade changelog

## demo-v28 UI toggle + 2-minute demo script

- Fixed the **Hide demo panel / Show demo panel** bug. The panel toggle is now a dedicated control, not a Chat/Pitch tab, so hiding the Demo flow + Workflow map panel no longer causes the Pitch view to override the chat.
- Added `DEMO_CLIP_SCRIPT_2MIN.md` with a time-coded demo script, exact prompts, expected bot-response highlights, screen cuts, and overlay annotations.
- Bumped app/UI version to `demo-v28` / `UI v28`.

## demo-v27 workflow YAML fix

- Fixed GitHub Actions YAML indentation in all workflow files so deploy/debug/seed/verify/Teams workflows parse correctly.
- Kept the natural-read / explicit-write command model.

## demo-v26 natural read / external action routing

- Removed `/metrics` from the user-facing command set.
- Main demo uses natural read-only funnel prompts:
  - `show me the funnel metrics`
  - `why is approval the top risk?`
  - `break May approval drop down by reason`
  - `weekly meeting summary`
- Slash commands are reserved for external systems and utilities: `/jira`, `/confluence`, `/teams`, `/model`, `/help`.
- Kept `/query` as an optional advanced/audit command for raw SQL-style drilldowns.

## demo-v25 panel control

- Added a control to hide/show the Demo flow + Workflow map panel so the chat can use more horizontal space during recording.

## demo-v24 funnel-command cleanup

- Added audit query/formulas to the main funnel metrics report.
- Kept KPI reports query-backed while presenting them as business readouts.

## demo-v23 report consistency polish

- Made `/jira what is critical or off track right now?` deterministic.
- Removed confusing owner-load and empty Epic-level sections.
- Normalized user-facing wording from legacy `completion` to **Disbursement**.
- Filtered Epic container issues out of workload/unassigned task counts.

## demo-v22 pitch/FAQ and Audit SQL polish

- Reworked the in-app Pitch tab to answer product questions instead of duplicating the demo guide.
- Restored collapsed `Audit SQL` blocks for deterministic drilldowns.

## Earlier major improvements

- Renamed the user-facing bot to **Funnel Agent**.
- Default MaaS model set to `openai/gpt-oss-20b`; `/model` reports runtime config deterministically.
- Added smaller reconciled row-level mock data where daily/monthly totals match.
- Added value-at-risk impact ranking, idempotent Jira recovery tickets, Confluence weekly summaries, Teams posting, and monthly Jira/Confluence history seeds.
