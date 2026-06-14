# Demo prompts and expected chatbot behavior

Use these in the demo order. The goal is to show the whole operating loop:

```text
metric drift -> impact ranking -> drilldown -> recovery action -> weekly meeting summary
```

All numbers below come from the row-level synthetic CSV. May 2026 reconciles to:

```text
Traffic 800 -> Submission 216 -> Approval 24 -> Completion 23
```

The Submission -> Approval drop is therefore:

```text
216 submitted - 24 approved = 192 submitted users/entities that did not reach Approval
```

## 1. Funnel health / impact ranking

Prompt:

```text
show me the funnel metrics
```

Expected behavior:

- Intent: `metrics`.
- Shows the monthly funnel table.
- Latest month is `2026-05`.
- May values should be:
  - Traffic: `800`
  - Submission: `216`
  - Approval: `24`
  - Completion: `23`
  - Submission rate: `27.0%`
  - Approval rate: `11.1%`
  - Completion rate: `95.8%`
  - E2E rate: `2.9%`
- Should lead with the impact ranking.
- Top recovery priority should be Approval:
  - Approval rate: `11.1%` vs `15.0%` target
  - Gap: about `-3.9pp`
  - MoM drop: about `-4.0pp` from April
  - Estimated value at risk: about `108.1M VND`
- Submission should appear as the second risk:
  - Submission rate: `27.0%` vs `30.0%` target
  - Estimated value at risk: about `34.2M VND`

Use this prompt to prove Watchtower is not just a dashboard: it ranks the recovery priority by business impact.

## 2. Explain why Approval is the top risk

Prompt:

```text
why did approval drop?
```

Expected behavior:

- Intent: `analyst`.
- Should use the deterministic diagnostic SQL template, not free-form causal guessing.
- Template should be similar to `approval_diagnostic_contribution`.
- Output should compare Approval performance by product type and channel.
- It should say this is contribution analysis / concentration analysis, not causal proof.
- SQL should be shown at the bottom.

Use this prompt to show that the model explains SQL results, but Python/DuckDB generate the facts.

## 3. Drop-reason reconciliation

Prompt:

```text
break May down by drop reason
```

Expected behavior:

- Intent: `analyst`.
- Template: `approval_drop_reason_breakdown`.
- It should explain the Submission -> Approval loss only, not all funnel rows.
- It should show:
  - stage_start_total: `216`
  - stage_passed_total: `24`
  - stage_drop_total: `192`
- Expected drop reason counts:

| Drop reason | Dropped users/entities |
|---|---:|
| `policy_check` | 90 |
| `docs_invalid` | 46 |
| `eligibility_check` | 38 |
| `docs_abandoned` | 18 |
| **Total** | **192** |

Use this prompt to show the data is internally consistent: every submitted-but-not-approved row is accounted for.

## 4. Daily-volume reconciliation

Prompt:

```text
show daily volume in May
```

Expected behavior:

- Intent: `analyst`.
- Template: `daily_volume`.
- It should return 31 daily rows for May.
- The daily rows should sum back to the May monthly totals:

```text
Traffic/applications: 800
Submitted: 216
Approved: 24
Completed: 23
```

- SQL should be shown.

Use this prompt to show that daily and monthly data come from the same row-level source of truth.

## 5. Recovery action / Jira loop

Prompt:

```text
flag the drops and assign owners to investigate
```

Expected behavior:

- Intent: `flag`.
- It should flag Approval and Submission because both are below target.
- Approval should be listed first because it has the higher value-at-risk estimate.
- If writes are disabled:
  - It should say writes are off and only flag the stages.
- If `ALLOW_WRITES=true` and Jira is configured:
  - It should create or update one investigation per stage + metric + month.
  - It should not create duplicate investigations if one already exists.
  - Jira descriptions/comments should include an investigation contract with stage, metric, evidence, expected value, owner if found, due date, confidence, and success check.

Use this prompt to show why this is an agent workflow, not a normal chatbot answer.

## 6. Manager execution view

Prompt:

```text
what is critical or off track right now?
```

Expected behavior:

- Intent: `oversight`.
- Should summarize Jira execution risk:
  - blocked work
  - overdue work
  - due-soon work
  - owners / Epic grouping
- Should quote Jira issue keys and owners from the synthetic workspace.
- Should not invent issue keys if Jira is unavailable.

Use this prompt to connect funnel drift with current execution risk.

## 7. Confluence / weekly meeting summary

Prompt:

```text
weekly meeting summary
```

Expected behavior:

- Intent: `weekly`.
- Should produce meeting-ready markdown with sections like:
  - Executive summary
  - Impact-ranked risks
  - Execution follow-up
  - Decisions / Confluence context
  - Proposed agenda
- Should include the Approval risk, Submission secondary risk, Jira follow-up, and recent Confluence context when available.

Use this prompt to show the weekly operating rhythm: the agent prepares the meeting from metrics + Jira + Confluence.

## 8. Optional Confluence write demo

Prompt:

```text
publish weekly meeting summary to Confluence
```

Expected behavior:

- Intent: `weekly`.
- If writes are disabled, it should draft the summary and clearly say it did not publish because `ALLOW_WRITES=false`.
- If writes are enabled and Confluence is configured, it should create or update a page titled like:

```text
Weekly Funnel Watchtower Summary - YYYY-MM-DD
```

Use this only if the demo workspace is safe and seeded.

## Fallback prompts if time is short

For a 2-3 minute demo clip, use only these four:

```text
show me the funnel metrics
why did approval drop?
flag the drops and assign owners to investigate
weekly meeting summary
```

Those four prompts demonstrate: detection, diagnosis, action, and meeting follow-up.

## Blocked-status clarification prompt

Prompt:

```text
what does blocked mean here and what is it blocking?
```

Expected behavior:

- Intent: `sprint` or `oversight`.
- It should clarify that `blocked` is a label/execution flag, not necessarily the Jira workflow status.
- It should say a task can be `workflow status = To Do` and also `label = blocked`.
- For the seeded blockers, it should explain:
  - Completion timestamp mismatch is blocked by verification status-map alignment from the partner feed, and it blocks reliable Completion timestamp reconciliation / final-outcome reporting.
  - Missing E2E funnel records is blocked by upstream event-feed/backfill from the data platform, and it blocks complete E2E funnel-log coverage / weekly metric confidence.
- If Jira lacks blocker details, the bot should say the blocker detail is not specified rather than inventing one.
