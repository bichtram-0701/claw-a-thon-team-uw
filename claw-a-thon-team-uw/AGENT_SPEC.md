# Lending Portfolio Watchdog — Agent Spec (draft for team review)

**Track:** Data Analysis | **Team:** UW | **Competition:** Claw-a-thon 2026

## Problem

Lending teams track portfolio health manually: exporting data, building the same
overdue/NPL pivot tables every week, and eyeballing for risky accounts. Deterioration
in a segment is often spotted weeks late, after accounts have already rolled into NPL.

## User

Portfolio / risk analysts and lending team leads who need daily visibility without
manual report building.

## What the agent does

1. **Q&A over the portfolio** — ask in plain language, get analysis:
   - "How is the portfolio doing this month?"
   - "Which segment has rising risk?" → *recent motorbike loans: 32% overdue/NPL vs 12.5% for older vintages*
   - "Compare provinces" → *Binh Duong (18.9%) and Dong Nai (18.4%) underperform HCMC (9.0%)*
2. **Watchdog alerts** — automatically flags accounts about to cross critical
   thresholds (e.g., 14 accounts at 85–90 DPD, about to become NPL) and explains why they matter.
3. **Weekly summary** — generates a manager-ready portfolio health report on request.
4. **(Bonus, if time allows) Jira action** — files a Jira ticket per flagged account
   on a free Atlassian Cloud workspace, demonstrating analysis → action.

## Demo script (2–3 min)

1. (20s) Problem: show messy manual workflow, one sentence.
2. (60s) Ask the 3 Q&A questions above; agent answers with numbers from the data.
3. (40s) Trigger watchdog: agent lists the near-90-DPD accounts and drafts the alert.
4. (30s) Generate weekly summary. (+ Jira ticket creation if bonus is in.)
5. (10s) Close: "synthetic data today, adapter swaps in real sources tomorrow."

## Architecture

```
User ──> Agent (AgentBase, MaaS model: Gemma/Qwen)
              │
              ├── Data Adapter  ←  data/loan_portfolio_synthetic.csv   (competition)
              │                 ←  internal lending DB / API           (post-competition, with BU approval)
              ├── Analysis tools (pandas: aggregation, vintage & DPD analysis)
              └── Action tools  (report writer; optional Jira Cloud connector)
```

The **adapter layer** is the key design choice: the agent never knows where data
comes from. Swapping CSV → real source later requires no change to agent logic.

## Rule compliance

- **Data:** 100% synthetic (seeded generator, 800 fake loans, no PII, no real customers) — rulebook §data rules.
- **Public repo:** no credentials, internal URLs, real schemas, or proprietary risk rules. Secrets via env vars only.
- **Models:** MaaS (Gemma/Qwen) via competition API tokens.
- **IP note (§9.2):** GreenNode owns the Contest Product. Generic engine only in repo;
  BU-specific business rules added privately post-competition.

## Dataset

`data/loan_portfolio_synthetic.csv` — 800 loans: id, product (personal/motorbike/
consumer durable/salary advance), segment, province, origination date, principal,
rate, term, outstanding, days past due, status. Embedded patterns so demo answers
are interesting: recent motorbike vintage deterioration, two weak provinces,
14 accounts near the 90-DPD cliff.

## ≤300-char use case description (draft for submission form)

> Lending teams build the same overdue/NPL reports manually and spot segment
> deterioration weeks late. Portfolio Watchdog answers portfolio questions in plain
> language, auto-flags accounts nearing NPL, and writes weekly summaries — turning
> hours of manual analysis into minutes. (287 chars)
