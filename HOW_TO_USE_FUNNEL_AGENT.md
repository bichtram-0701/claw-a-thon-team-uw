# How to use Funnel Agent

Funnel Agent follows a simple rule:

> Ask naturally for read-only insight. Use slash commands when the agent touches an external workflow.

## Main commands

| Command | Use for |
|---|---|
| `/jira` | Owners, blockers, off-track work, create/update Jira investigations |
| `/confluence` | Publish/search/update Confluence pages |
| `/teams` | Teams reminders for blocked/overdue/off-track work |
| `/model` | Runtime/model info |
| `/help` | Usage and database guidance |

Optional advanced commands:

| Command | Use for |
|---|---|
| Ask naturally | Funnel KPIs, MoM, top risk, value at risk, and drilldowns |
| `/query` | Advanced audit/debug data queries and SQL templates |


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
show me the funnel metrics
why is approval the top risk?
break May approval drop down by reason
/jira flag the drops and assign owners to investigate
/jira what is critical or off track right now?
/jira what does blocked mean here and what is it blocking?
weekly meeting summary
/confluence publish weekly meeting summary to Confluence
/teams post off-track blockers
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
| volume | traffic count, stage counts, or VND value | `show daily volume in May` |
| drop | any transition or MoM rate decline | `break May approval drop down by reason` |
| owner | Epic assignee or operational stage owner | `/jira explain stage ownership structure` |
| blocked | Jira label/flag or workflow status | `/jira what does blocked mean here and what is it blocking?` |

Read-only funnel and weekly-summary prompts work naturally. Write actions require `/jira`, `/confluence`, or `/teams`.
