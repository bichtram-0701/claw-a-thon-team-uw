# Funnel Watchtower - Pitch Deck Outline

Use this when building slides or a 2-3 minute demo video. The deck should be structured around the objections judges will ask, not around a feature list.

## 1. Title

**Funnel Watchtower**

**Turn funnel drift into ranked, owned recovery actions.**

## 2. Where is the real bottleneck?

The bottleneck is not data or dashboards. The bottleneck is turning metric drift into accountable recovery work.

```text
Metric drops -> manager checks dashboard -> searches Jira -> searches Confluence -> pings team -> creates follow-up -> repeats for weekly meeting
```

## 3. Why agent, not normal chat?

Normal chat gives an answer. Watchtower runs the workflow.

| Normal chat | Funnel Watchtower |
|---|---|
| Needs pasted context | Pulls metric, Jira, and Confluence context |
| Summarizes what is provided | Computes target gap and value at risk |
| Gives advice | Creates or updates owned recovery action |
| No duplicate protection | Idempotent investigation logic |
| One-off response | Weekly recovery readout |

## 4. Why this workflow?

Because funnel recovery is recurring, cross-functional, and action-oriented.

```text
Detect drift -> Rank impact -> Find owner/blockers -> Create/update action -> Summarize decisions -> Prepare weekly readout
```

## 5. Demo scenario

Use the simple synthetic funnel:

```text
Traffic -> Submission -> Approval -> Disbursement
```

Say: the final stage can map to purchase, activation, contract signed, request completed, merchant live, or payout in another business.

Show:

```text
Top risk
Actual vs target
Estimated value at risk
Owner
Jira execution risk
Recommended action
```

## 6. Live demo flow

Use four prompts maximum:

```text
1. show me the funnel metrics
2. rank the target misses by value at risk
3. flag the drops and assign owners to investigate
4. weekly meeting summary
```

If writes are enabled, add:

```text
publish weekly meeting summary to Confluence
```

## 7. Architecture / reliability

Do not frame this as model-specific on the main slide. The LLM is a replaceable layer.

Use this line:

**The LLM understands and explains. Deterministic tools compute, validate, rank, and write.**

```text
User question
  -> LLM-first intent router
  -> deterministic tools
     - funnel metrics
     - value-at-risk ranking
     - SQL templates
     - Jira ownership / blockers
     - Confluence weekly summary
     - duplicate-ticket prevention
  -> LLM narration
  -> Jira / Confluence / Teams
```

## 8. Defensibility

The moat is the Funnel Execution Graph:

```text
metric -> stage -> target -> owner -> initiative -> blocker -> decision -> outcome
```

Generic AI can summarize tools. Watchtower encodes how the team operates the funnel and closes the recovery loop.

## Closing line

**Funnel Watchtower is not another dashboard and not just a chatbot. It is an execution layer for owned business metrics.**
