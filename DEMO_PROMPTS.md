# Funnel Watchtower demo prompts

Use the chips in this order. The first 8 prompts are the main 2-3 minute demo; the remaining prompts are optional validation/add-on prompts.


## Routing policy

The demo chips intentionally use command prefixes. Prefixed prompts route deterministically:

```text
metrics:      metric tables, MoM, top risk, value at risk
sql:          safe DuckDB templates and data drilldowns
jira:         owner/blocker views and Jira write actions
confluence:   weekly summaries, Confluence read/publish flows
teams:        Teams reminders
help:         usage/database guidance
```

Non-prefixed read-only prompts still work in `ROUTING_MODE=warn`, but the bot shows a routing warning. Non-prefixed write actions are blocked and ask the user to resend with the correct prefix.

## Main demo sequence

1. `metrics: show me the funnel metrics`
   - Expected: monthly funnel table with `MoM Abs` and `MoM Pct` columns, impact ranking, and top recovery priority.
   - Latest month should be May 2026: Traffic 800, Submission 216, Approval 24, Completion 23.
   - Top recovery priority should be Approval, with about 108.1M VND estimated value at risk.

2. `metrics: why is approval the top risk?`
   - Expected: concise explanation of the impact ranking: target gap, MoM movement, estimated value at risk, owner/execution context.
   - This is not causal proof; it explains why Approval ranks first.

3. `sql: break May approval drop down by reason`
   - Expected: Submission -> Approval reconciliation.
   - Should state 216 submitted, 24 approved, 192 dropped before Approval.
   - Drop reasons should sum to 192.

4. `jira: flag the drops and assign owners to investigate`
   - Expected: creates or updates idempotent Jira investigations for Approval and Submission.
   - Issue keys should be clickable `UW-*` Jira links.

5. `jira: what is critical or off track right now?`
   - Expected: manager execution view combining metric risk, blocked/overdue Jira items, owners, and blocker context.

6. `jira: what does blocked mean here and what is it blocking?`
   - Expected: explains that blocked is a Jira label/execution flag, not necessarily the workflow status, then lists `blocked_by` / `blocks` details.

7. `confluence: weekly meeting summary`
   - Expected: deterministic weekly readout with executive summary, impact ranking, needs attention, completed work, Confluence context, and agenda.

8. `confluence: publish weekly meeting summary to Confluence`
   - Expected: creates/updates the Confluence weekly page and returns a short confirmation link instead of repeating the full summary.

## Optional validation / add-on prompts

- `teams: post off-track blockers`
  - Posts or previews a Teams reminder for blocked/overdue work.
  - If `TEAMS_WEBHOOK_URL` is configured and `ALLOW_WRITES=true`, it posts to Teams. Otherwise it shows the reminder preview and explains what is missing.

- `metrics: compare April and May performance`
  - Shows a specific month-pair comparison. Useful if someone asks for MoM details beyond the default metrics table.

- `sql: show daily volume in May`
  - Shows daily stage counts that reconcile back to the May monthly totals.

- `help: how should I ask questions?`
  - Shows the usage guide and recommended prompt pattern.

## What not to use in the main demo

- Do not use exploratory prompts like `compare March and April` unless you specifically want to show arbitrary month-pair comparison.
- Do not include Vietnamese prompts in the demo path yet.
- Avoid repeated weekly summaries; show the summary once, then publish it.
