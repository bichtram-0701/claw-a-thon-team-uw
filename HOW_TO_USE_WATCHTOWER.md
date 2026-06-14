# How to use Funnel Watchtower

Funnel Watchtower supports natural questions, but it works best when a prompt includes three pieces:

```text
action + stage/metric + time period
```

Examples:

```text
show me the funnel metrics
why is approval the top risk?
break May approval drop down by reason
flag the drops and assign owners to investigate
what is critical or off track right now?
weekly meeting summary
publish weekly meeting summary to Confluence
post off-track blockers to Teams
compare April and May performance
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
post off-track blockers to Teams
```

This posts blocked/overdue work to Teams when `TEAMS_WEBHOOK_URL` is configured and `ALLOW_WRITES=true`. If Teams is not configured, the bot returns a preview so the demo does not fail.

Other supported variants:

```text
post blocked work to Teams
send overdue reminder to Teams
send due soon reminder to Teams
```

## Demo sequence

1. `show me the funnel metrics`
2. `why is approval the top risk?`
3. `break May approval drop down by reason`
4. `flag the drops and assign owners to investigate`
5. `what is critical or off track right now?`
6. `what does blocked mean here and what is it blocking?`
7. `weekly meeting summary`
8. `publish weekly meeting summary to Confluence`

Optional add-ons:

```text
post off-track blockers to Teams
compare April and May performance
show daily volume in May
how should I ask questions?
```
