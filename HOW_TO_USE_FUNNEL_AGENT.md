# How to use Funnel Agent

Funnel Agent supports natural language, but slash commands make routing auditable and safe. Use this pattern:

```text
/slash-command + action + stage/metric + time period
```

## Commands

| Command | Use for |
|---|---|
| `/funnel` | Funnel KPIs, MoM comparison, top risk, value at risk, and safe data drilldowns such as daily volume/drop reasons |
| `/jira` | Owners, blockers, off-track work, create/update Jira investigations |
| `/confluence` | Weekly meeting summaries and Confluence publishing |
| `/teams` | Teams reminders for blocked/overdue/off-track work |
| `/model` | Runtime/model info |
| `/help` | Usage and database guidance |
| `/query` | Optional alias for data drilldowns; `/funnel` is preferred for the demo |

## Funnel stages

```text
Traffic -> Submission -> Approval -> Disbursement
```

| Stage | Meaning |
|---|---|
| Traffic | User/entity enters the funnel |
| Submission | User/entity successfully submits to the partner/system |
| Approval | Submitted user/entity is approved |
| Disbursement | Approved user/entity reaches the final disbursement event |

## Recommended demo prompts

```text
/funnel show me the funnel metrics
/funnel why is approval the top risk?
/funnel break May approval drop down by reason
/jira explain stage ownership structure
/jira flag the drops and assign owners to investigate
/jira what is critical or off track right now?
/jira what does blocked mean here and what is it blocking?
/confluence weekly meeting summary
/confluence publish weekly meeting summary to Confluence
/teams post off-track blockers
/funnel what was done in March to improve approval?
/model
```

## Ownership model

Funnel Agent uses an **Epic -> stage owner -> task assignee** convention.

- Each funnel stage has a Jira Epic.
- The Jira Epic issue itself may be unassigned.
- The operational stage owner is inferred from owner labels / assignees on work under that stage.
- If `/jira create ...` or `/jira flag ...` does not mention an assignee, Funnel Agent defaults to the operational stage owner and says so in the response.

## Ambiguous words

| Word | Could mean | Safer prompt |
|---|---|---|
| volume | traffic count, stage counts, or VND value | `/funnel show daily volume in May` |
| drop | any transition or MoM rate decline | `/funnel break May approval drop down by reason` |
| owner | Epic assignee or operational stage owner | `/jira explain stage ownership structure` |
| blocked | Jira label/flag or workflow status | `/jira what does blocked mean here and what is it blocking?` |

Read-only prompts without a slash command still work in `ROUTING_MODE=warn`, but the bot shows an interpretation warning. Write actions require the explicit command.
