# How to use Funnel Watchtower

Funnel Watchtower supports natural read-only questions, but for reliable workflow execution use a command prefix plus the request:

```text
prefix + action + stage/metric + time period
```

Supported prefixes:

| Prefix | Use for |
|---|---|
| `metrics:` | Metric tables, MoM comparison, top risk, value at risk |
| `sql:` | Safe data drilldowns: daily volume, drop reasons, channel/product breakdowns |
| `jira:` | Owners, blockers, off-track work, create/update Jira investigations |
| `confluence:` | Weekly meeting summaries and Confluence publishing |
| `teams:` | Teams reminders for blocked/overdue/off-track work |
| `help:` | Usage and database guidance |

In `ROUTING_MODE=warn`, non-prefixed read-only prompts still work with a routing warning. Non-prefixed write actions require the explicit prefix.

Examples:

```text
metrics: show me the funnel metrics
metrics: why is approval the top risk?
sql: break May approval drop down by reason
jira: flag the drops and assign owners to investigate
jira: what is critical or off track right now?
confluence: weekly meeting summary
confluence: publish weekly meeting summary to Confluence
teams: post off-track blockers
metrics: compare April and May performance
```

## Funnel stages

| Stage | Meaning |
|---|---|
| Traffic | Users/entities entering the funnel |
| Submission | Users/entities that submitted |
| Approval | Submitted users/entities that were approved |
| Completion | Approved users/entities that completed the final outcome |

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
teams: post off-track blockers
```

This posts blocked/overdue work to Teams when `TEAMS_WEBHOOK_URL` is configured and `ALLOW_WRITES=true`. If Teams is not configured, the bot returns a preview so the demo does not fail.

Other supported variants:

```text
teams: post blocked work
teams: send overdue reminder
teams: send due soon reminder
```

## Demo sequence

1. `metrics: show me the funnel metrics`
2. `metrics: why is approval the top risk?`
3. `sql: break May approval drop down by reason`
4. `jira: flag the drops and assign owners to investigate`
5. `jira: what is critical or off track right now?`
6. `jira: what does blocked mean here and what is it blocking?`
7. `confluence: weekly meeting summary`
8. `confluence: publish weekly meeting summary to Confluence`

Optional add-ons:

```text
teams: post off-track blockers
metrics: compare April and May performance
sql: show daily volume in May
help: how should I ask questions?
```
