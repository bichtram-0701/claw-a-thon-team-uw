# Funnel Watchtower - pitch

## One-line pitch

**Funnel Watchtower turns funnel drift into ranked, owned recovery actions.**

## Core insight

The bottleneck is not knowing that a metric moved. Dashboards already do that.

The bottleneck is turning metric drift into accountable recovery work: deciding which drop matters most, how much value is at risk, who owns recovery, what work is blocked, and what needs to be discussed in the weekly meeting.

## 30-second pitch

Every business team owns a funnel: marketing leads, product onboarding, sales pipeline, merchant activation, operations requests, or application flows. Dashboards show when metrics move, but managers still have to connect metrics, Jira work, Confluence decisions, and team follow-up manually.

Funnel Watchtower closes that loop. It detects target drift, estimates value at risk, ranks the highest-impact funnel problem, finds the owner and execution risk in Jira, summarizes relevant Confluence context, and creates or updates the recovery action. It also prepares the weekly meeting readout so the team can follow through.

The LLM is a replaceable interface layer. It understands the user's question and explains verified facts. Deterministic tools compute the numbers, rankings, SQL diagnostics, and write guards.

## 100-200 word submission pitch

Business teams do not only need to know that a funnel metric moved. They need to know which movement matters most, how much value is at risk, who owns recovery, what work is already in flight, whether that work is blocked, and what should be discussed in the weekly meeting.

**Funnel Watchtower** is an execution intelligence layer for owned business funnels. It computes funnel conversion, target gaps, month-over-month anomalies, and estimated value at risk from synthetic data. It then connects those signals to Jira initiatives, Confluence decisions, Teams notifications, and weekly meeting summaries. When a metric slips, it ranks the issue by business impact and execution risk, identifies the stage owner, and can open or update one Jira investigation for that stage, metric, and month.

The model only routes, extracts bounded fields, and narrates verified facts. The math, issue keys, owners, SQL templates, duplicate-ticket prevention, and write decisions are validated by code. Generic chat can answer questions. Funnel Watchtower runs the recovery workflow.

## Why agent, not normal Claude/ChatGPT?

Normal chat is good at answering a one-off question. This problem is a recurring operating loop across multiple systems.

| Normal chat | Funnel Watchtower |
|---|---|
| Answers when asked | Runs a repeatable recovery workflow |
| Needs pasted context | Pulls metrics, Jira, and Confluence context |
| Summarizes text | Computes target gaps and value at risk |
| Gives advice | Opens or updates owned recovery work |
| Can duplicate tasks | Uses idempotent investigation logic |
| Has no weekly operating state | Produces a weekly recovery readout |

**A chatbot gives an answer. Watchtower closes the loop.**

## Why this workflow?

Funnel recovery is recurring, cross-functional, and action-oriented. Every week, managers need to know:

1. Which funnel stage is drifting?
2. Which drift has the highest business impact?
3. Who owns recovery?
4. What Jira work exists, and is it blocked or overdue?
5. What Confluence decisions explain the current direction?
6. What should be on the weekly meeting agenda?

That is why the workflow is:

```text
Detect drift -> Rank impact -> Find owner/blockers -> Create/update action -> Summarize decisions -> Prepare weekly readout
```

## What is the real bottleneck?

The real bottleneck is **metric-to-action translation**.

Metrics, tasks, documents, and chat already exist. The hard part is connecting them quickly enough that the team can recover before the target is missed.

## Why this is defensible

Generic assistants can summarize Jira and Confluence. Watchtower adds the missing business operating layer:

- **Funnel ontology**: stages, metrics, targets, owners, and Epics are explicit.
- **Value-at-risk math**: target gaps are converted into estimated business impact.
- **Execution-risk scoring**: Jira blockers, overdue work, and open workload change the priority.
- **Initiative contracts**: recovery tasks declare metric, expected lift, value, evidence, owner, and success check.
- **Idempotent action loop**: one open investigation per stage + metric + month, updated instead of duplicated.
- **Weekly operating rhythm**: the agent prepares and can publish the Confluence weekly meeting readout.
- **Model-agnostic design**: the LLM can be replaced; the operating logic stays in code.

The moat is the **Funnel Execution Graph**:

```text
metric -> stage -> target -> owner -> initiative -> blocker -> decision -> outcome
```

Over time, this can learn which interventions actually recover which metrics.

## Objection handling

### "Isn't this just Jira AI or a dashboard?"

No. A dashboard shows metric movement. Jira shows work. Confluence stores decisions. Watchtower connects them into one recovery loop: impact ranking, owner, blocker, existing work, investigation, and weekly follow-up.

### "Why not just use a normal chatbot?"

Because the user would still have to paste data, search Jira, search Confluence, check duplicates, create the ticket, and prepare the weekly meeting summary. Watchtower does those steps as a governed workflow.

### "Does it depend on a specific model?"

No. The current runtime can use the approved MaaS model, but the LLM layer is replaceable. The business logic is deterministic: Python and SQL compute the metrics, value at risk, SQL templates, duplicate checks, and write guards. The LLM understands and explains; code computes and validates.

### "Does it prove causality?"

No, and it should not claim to. Root-cause drilldowns are contribution analysis: where the drop is concentrated by channel, product, or drop reason. The agent says "concentrated in" unless a causal test exists.

## Demo flow

1. Ask: `metrics: show me the funnel metrics`.
   - It shows the latest conversion table, MoM columns, and the top value-at-risk priority.
2. Ask: `why is approval the top risk?`.
   - It explains the ranking: target gap, MoM deterioration, and value at risk.
3. Ask: `break May approval drop down by reason`.
   - It reconciles the 192 submitted-but-not-approved rows by drop reason.
4. Ask: `flag the drops and assign owners to investigate`.
   - It creates or updates one investigation per stage, with a structured contract.
5. Ask: `what is critical or off track right now?`.
   - It connects the metric risk to Jira blockers, owners, and overdue work.
6. Ask: `what does blocked mean here and what is it blocking?`.
   - It explains blocker semantics and the dependency behind each blocked task.
7. Ask: `teams: post off-track blockers`.
   - It posts the blocked/overdue Jira digest to the configured Teams channel.
8. Ask: `confluence: weekly meeting summary`.
   - It drafts the weekly readout: executive summary, risks, blockers, Confluence context, agenda.
9. Ask: `confluence: publish weekly meeting summary to Confluence`.
   - It creates or updates the weekly meeting page.

## Final positioning

**Funnel Watchtower is not another dashboard and not just a chatbot. It is an execution layer for owned business metrics: it detects drift, ranks what matters, assigns ownership, and keeps the recovery loop moving.**
