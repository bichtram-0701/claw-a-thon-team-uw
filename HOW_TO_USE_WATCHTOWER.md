# How to use Funnel Watchtower

Funnel Watchtower supports natural read-only questions, but for reliable workflow execution use a command prefix plus the request:

```text
slash command + action + stage/metric + time period
```

Supported slash commands:

| Prefix | Use for |
|---|---|
| `/metrics` | Metric tables, MoM comparison, top risk, value at risk |
| `/query` | Safe data drilldowns: daily volume, drop reasons, channel/product breakdowns |
| `/jira` | Owners, blockers, off-track work, create/update Jira investigations |
| `/confluence` | Weekly meeting summaries and Confluence publishing |
| `/teams` | Teams reminders for blocked/overdue/off-track work |
| `/help` | Usage and database guidance |

In `ROUTING_MODE=warn`, non-prefixed read-only prompts still work with a routing warning. Non-slash-command write actions require the explicit slash command.

Examples:

```text
/metrics show me the funnel metrics
/metrics why is approval the top risk?
/query break May approval drop down by reason
/jira explain stage ownership structure
/jira flag the drops and assign owners to investigate
/jira what is critical or off track right now?
/confluence weekly meeting summary
/confluence publish weekly meeting summary to Confluence
/teams post off-track blockers
/metrics compare April and May performance
```

## Funnel stages

| Stage | Meaning |
|---|---|
| Traffic | Users/entities entering the funnel |
| Submission | Users/entities that submitted |
| Approval | Submitted users/entities that were approved |
| Completion | Approved users/entities that completed the final outcome |

## Jira ownership model

Watchtower uses an **Epic → stage owner → task assignee** convention. Each funnel stage has a Jira Epic. Open work under that stage reveals the operational stage owner. When `/jira create ...` or `/jira flag ...` does not name an assignee, Watchtower defaults to that stage owner and says so in the response.

Use:

```text
/jira explain stage ownership structure
```

before the Jira write step in the demo if you want to make this explicit.

## Safe defaults

| Ambiguous term | Default behavior |
|---|---|
| `volume` | Return all funnel-stage counts unless a stage is specified |
| `drop reason` | Highlight the current highest-risk transition, usually Submission -> Approval in the demo |
| `top risk` | Explain the deterministic impact ranking |
| `blocked` | Explain Jira blocker labels plus `blocked_by` and `blocks` details when available |
| `MoM` | Standard metrics include latest `MoM Abs` and `MoM Pct`; explicit comparison prompts compare the requested months |

## Teams prompts

Use:

```text
/teams post off-track blockers
```

This posts blocked/overdue work to Teams when `TEAMS_WEBHOOK_URL` is configured and `ALLOW_WRITES=true`. If Teams is not configured, the bot returns a preview so the demo does not fail.

Other supported variants:

```text
/teams post blocked work
/teams send overdue reminder
/teams send due soon reminder
```

## Demo sequence

1. `/metrics show me the funnel metrics`
2. `/metrics why is approval the top risk?`
3. `/query break May approval drop down by reason`
4. `/jira explain stage ownership structure`
5. `/jira flag the drops and assign owners to investigate`
6. `/jira what is critical or off track right now?`
7. `/jira what does blocked mean here and what is it blocking?`
8. `/confluence weekly meeting summary`
9. `/confluence publish weekly meeting summary to Confluence`

Optional add-ons:

```text
/teams post off-track blockers
/metrics compare April and May performance
/query show daily volume in May
/help how should I ask questions?
```
