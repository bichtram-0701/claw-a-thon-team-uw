# Funnel Agent demo prompts

Use the demo panel in this order. The main demo uses natural language for read-only insight and slash commands only when Funnel Agent touches an external workflow.

For a time-coded voiceover and screen-recording script, see `DEMO_CLIP_SCRIPT_2MIN.md`.

## Routing policy

```text
Read-only funnel intelligence: ask naturally
Jira work/actions:      /jira
Confluence publish/search:  /confluence
Teams notifications:     /teams
Runtime info:         /model
Help/guidance:        /help
```

For read-only funnel insight, ask naturally. `/query` remains available as an advanced audit/debug mode if someone explicitly wants raw SQL, but it is not part of the main demo.

Non-prefixed write actions are blocked and ask the user to resend with the correct external-action command.

## Main demo sequence

1. `show me the funnel metrics`
  - Expected: monthly funnel table with `MoM Abs` and `MoM Pct` columns, impact ranking, and top recovery priority.
  - Latest month should be May 2026: Traffic 800, Submission 216, Approval 24, Disbursement 23.
  - Top recovery priority should be Approval, with about 108.1M VND estimated value at risk.
  - Includes a collapsed audit query/formulas section.

2. `why is approval the top risk?`
  - Expected: concise explanation of the impact ranking: target gap, MoM movement, estimated value at risk, owner/execution context.
  - This is not causal proof; it explains why Approval ranks first.

3. `break May approval drop down by reason`
  - Expected: Submission -> Approval reconciliation.
  - Should state 216 submitted, 24 approved, 192 dropped before Approval.
  - Drop reasons should sum to 192.
  - Includes collapsed Audit SQL.

4. `/jira flag the drops and assign owners to investigate`
  - Expected: creates or updates idempotent Jira investigations for Approval and Submission.
  - If no assignee is mentioned, it defaults to the operational stage owner and says so.
  - Issue keys should be clickable `UW-*` Jira links.

5. `/jira what is critical or off track right now?`
  - Expected: manager execution view combining metric risk, blocked/overdue Jira items, owners, and blocker context.

6. `/jira what does blocked mean here and what is it blocking?`
  - Expected: explains that blocked is a Jira label/execution flag, not necessarily the workflow status, then lists `blocked_by` / `blocks` details.

7. `weekly meeting summary`
  - Expected: deterministic weekly readout with executive summary, impact ranking, needs attention, completed work, Confluence context, and agenda.

8. `/confluence publish weekly meeting summary to Confluence`
  - Expected: creates/updates the Confluence weekly page and returns a short confirmation link instead of repeating the full summary.

9. `/teams post off-track blockers`
  - Expected: posts or previews a Teams reminder for blocked/overdue work.

## Optional validation / add-on prompts

- `/teams post due-soon reminders`
- `compare April and May performance`
- `show daily volume in May`
- `what was done in March to improve approval?`
- `/jira give me all the tasks along with assignee and due date and status`
- `/model`
- `/help how should I ask questions?`
- `/query show SQL for May approval drop reason`

## What not to use in the main demo

Avoid legacy data commands in the main demo. Ask funnel questions naturally instead.
