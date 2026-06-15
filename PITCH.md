# Funnel Agent - pitch

## One-line pitch

**Funnel Agent turns funnel drift into owned recovery work.**

## What is Funnel Agent?

Funnel Agent is an execution agent for owned business funnels. It connects funnel metrics, Jira recovery work, Confluence decision memory, and Teams notifications into one operating loop:

```text
Detect -> Diagnose -> Assign -> Summarize -> Notify
```

The demo funnel is:

```text
Traffic -> Submission -> Approval -> Disbursement
```

The product is not limited to this funnel. The same pattern applies to marketing acquisition, product onboarding, sales pipelines, merchant activation, and operations workflows.

## What problem does it solve?

Dashboards show what changed. Jira shows what people are doing. Confluence stores decisions. Teams carries reminders.

The problem is that these systems do not automatically answer:

1. Which metric movement matters most?
2. How much value is at risk?
3. Who owns recovery?
4. Is recovery work already in flight?
5. Is anything blocked or overdue?
6. What should go into the weekly meeting?
7. Who needs to be notified?

The real bottleneck is **metric-to-action translation**.

## Why agent, not normal ChatGPT?

A chatbot answers a question. Funnel Agent runs a governed workflow.

| Normal chat | Funnel Agent |
|---|---|
| Needs the user to bring context | Pulls metrics, Jira, and Confluence context |
| Summarizes text | Computes target gaps, MoM movement, and value at risk |
| Gives advice | Creates or updates owned Jira recovery work |
| Can duplicate tasks | Uses idempotent investigation logic |
| Has no operating state | Produces weekly readouts and Teams follow-up |
| May guess | Uses explicit commands, safe defaults, and deterministic tools |

The LLM is a replaceable interface layer. The workflow logic is the product.

## Workflow principles

### Metrics

The metrics layer computes funnel health, conversion rates, month-over-month changes, target misses, value at risk, and drop-reason reconciliation.

### Jira

Jira is the execution system of record. Funnel Agent uses an:

```text
Epic -> stage owner -> task assignee
```

structure. If a Jira write does not mention an assignee, the agent defaults to the operational stage owner.

### Confluence

Confluence is the weekly decision and meeting memory. The weekly readout captures risks, blockers, owners, completed work, decisions, and next actions.

### Teams

Teams is the notification layer. It can post off-track blockers, Jira task changes, due-soon reminders, and stale-task digests.

## Defensibility

Generic AI can summarize Jira. Funnel Agent adds the business operating layer:

- funnel stages and targets
- value-at-risk formulas
- stage ownership
- Jira idempotency and assignment defaults
- drop-reason reconciliation
- Confluence weekly memory
- Teams accountability loop

The moat is the **Funnel Execution Graph**:

```text
metric -> target -> stage -> owner -> initiative -> blocker -> decision -> outcome
```

## FAQ

### Is this just another dashboard?

No. A dashboard stops at reporting. Funnel Agent connects the metric to business impact, owner, recovery work, blockers, weekly readout, and team notification.

### Is this just Jira AI?

No. Jira knows tickets. It does not know the funnel target gap, value-at-risk estimate, drop-reason reconciliation, or weekly metric recovery loop.

### Does the LLM calculate the numbers?

No. Python and SQL compute the metrics, MoM changes, value at risk, SQL templates, Jira dedupe, and write guards. The model routes, extracts bounded fields, and explains verified facts.

### Does it prove causality?

No. The diagnostic layer is contribution analysis and reconciliation. It shows where the drop is concentrated, not whether a reason caused the drop.

### Why slash commands?

Because the agent can write to Jira, Confluence, and Teams. Slash commands make workflow routing explicit and safer. Read-only natural-language prompts still work with warnings.

### Why does the Jira Epic itself sometimes look unassigned?

The demo separates the raw Jira Epic assignee from the operational stage owner. The operational owner is inferred from the Epic -> stage owner -> task assignee structure and is used for recovery assignments.

### What is missing from the current demo?

The main future feature is closed-loop outcome learning: after a Jira recovery task is completed, Funnel Agent should compare before/after metrics and classify the action as worked, partially worked, failed, or inconclusive.

## Final positioning

**Funnel Agent is not another dashboard and not just a chatbot. It is an execution layer for owned business metrics: it detects drift, ranks what matters, assigns ownership, and keeps the recovery loop moving.**
