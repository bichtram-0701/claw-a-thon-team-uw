# How to use Funnel Watchtower

Funnel Watchtower supports natural questions, but it works best when the prompt tells it three things:

```text
action + stage/metric + time period
```

Example:

```text
show daily volume in May
why did approval drop?
flag the approval drop and assign the owner
publish weekly meeting summary to Confluence
```

The agent is not just a general chatbot. It routes questions into structured tools for funnel metrics, safe SQL analysis, Jira execution state, Confluence summaries, and Jira/Confluence write actions. Clear stage and time-period language helps it pick the right tool.

## Funnel stages

| Stage | Meaning | Example prompts |
|---|---|---|
| Traffic | Users/entities entering the funnel | `show traffic volume in May` |
| Submission | Users/entities that submitted | `show submission rate this month` |
| Approval | Submitted users/entities that were approved | `why did approval drop?` |
| Completion | Approved users/entities that reached the final outcome | `show completion rate` |

The demo funnel is:

```text
Traffic -> Submission -> Approval -> Completion
```

## Recommended demo prompts

Use these in order for the demo:

```text
show me the funnel metrics
why did approval drop?
break May down by drop reason
show daily volume in May
flag the drops and assign owners to investigate
what is critical or off track right now?
what does blocked mean here and what is it blocking?
weekly meeting summary
publish weekly meeting summary to Confluence
```

## Good prompt patterns

### Metrics and impact

```text
show me the funnel metrics
what is the top funnel risk this month?
show value at risk
rank the funnel problems by business impact
```

### SQL-style analysis

```text
show daily volume in May
break May down by drop reason
show May volume by channel
show approval by product type
why did approval drop?
```

### Jira execution state

```text
what is critical or off track right now?
who is working on what?
what is blocked?
what does blocked mean here and what is it blocking?
```

### Actions

```text
flag the drops and assign owners to investigate
create a ticket to standardize the submission log schema
assign UW-23 to Mai
```

### Weekly operating rhythm

```text
weekly meeting summary
publish weekly meeting summary to Confluence
```

## Ambiguous words

Some words are useful but ambiguous. The agent has safe defaults, but more specific wording is better.

| Word | Could mean | Better prompt |
|---|---|---|
| volume | traffic, submitted, approved, completed, or all stage counts | `show daily funnel volume by stage in May` |
| drop | any transition in the funnel | `show Submission -> Approval drop reasons` |
| value | count or VND value | `show estimated value at risk` |
| completion | final stage of the generic funnel | `show completion rate in May` |

## Safe defaults

| Prompt | Default behavior |
|---|---|
| `daily volume in May` | Daily counts for all stages: Traffic, Submitted, Approved, Completed |
| `break May down by drop reason` | Highlights the highest-risk transition, currently Submission -> Approval |
| `why did approval drop?` | Runs deterministic contribution/diagnostic templates |
| `flag the drop` | Flags the highest impact-ranked target miss/drop |

## What the LLM does and does not do

The LLM helps understand the user's question and explain the results. It does not own the business facts.

Deterministic code computes:

```text
funnel metrics
target gaps
value at risk
SQL templates
Jira duplicate checks
Confluence page formatting
```

The model explains those verified results in manager-friendly language.
