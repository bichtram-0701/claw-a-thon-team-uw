# Submission form draft - Team UW

## Agent name
Funnel Agent

## Tagline
Turns funnel drift into ranked, owned recovery actions.

## Track
Agentic Assistant

## Problem
Business teams already have dashboards, Jira, Confluence, and chat. But when a funnel metric moves, the recovery workflow is still manual: managers must decide which drop matters most, estimate impact, find the owner, check whether work exists, read the latest decisions, and prepare follow-up for the weekly meeting.

The real bottleneck is metric-to-action translation.

## Solution
Funnel Agent is an execution intelligence agent for owned business funnels. Ask `/metrics show me the funnel metrics` and it computes conversion, target gaps, month-over-month anomalies, and estimated value at risk. Ask `/jira what is critical or off track right now?` and it links those risks to Jira owners, blockers, overdue work, and open initiatives. Ask `/jira flag it` and it creates or updates one Jira investigation per stage + metric + month with a structured initiative contract. Ask `/confluence weekly meeting summary` and it drafts, and optionally publishes, a Confluence readout with impact-ranked risks, execution follow-up, decisions, and agenda.

The LLM handles routing, extraction, and narration only. Python and SQL compute numbers, rankings, SQL templates, Jira writes, duplicate-ticket prevention, and Confluence publishing guards.

## Value
Watchtower compresses the manager's operating loop from dashboard -> Jira -> Confluence -> Teams into one accountable workflow: detect target drift, estimate business value at risk, rank the priority, identify the owner, open/update recovery work, and prepare the weekly readout. It is useful even with a replaceable internal model layer because the business truth is deterministic and auditable.

## Voter guide
Try:

```text
/metrics show me the funnel metrics
/metrics why is approval the top risk?
/query break May approval drop down by reason
/jira explain stage ownership structure
/jira flag the drops and assign owners to investigate
/jira what is critical or off track right now?
/jira what does blocked mean here and what is it blocking?
/teams post off-track blockers
/confluence weekly meeting summary
/confluence publish weekly meeting summary to Confluence
```

All demo data is synthetic. The row-level daily fixture is now the source of truth, so daily totals reconcile to the monthly funnel numbers.

## 100-200 word use case description
Business teams do not only need to know that a funnel metric moved. They need to know which movement matters most, how much value is at risk, who owns recovery, whether work is blocked, and what should be discussed in the weekly meeting.

Funnel Agent is an execution intelligence agent for owned funnels. The demo uses a simple four-stage funnel: Traffic -> Submission -> Approval -> Disbursement, but the pattern applies to marketing acquisition, product onboarding, sales pipeline, merchant activation, and operations workflows. It computes conversion, OKR target gaps, month-over-month drops, and estimated value at risk deterministically from synthetic data. It then links those signals to Jira initiatives, owners, blockers, Confluence decisions, Teams follow-up, and weekly meeting summaries. When a metric slips, Funnel Agent ranks the issue by business impact and execution risk, identifies the owner, and can open or update a Jira investigation with a structured initiative contract.

The LLM only routes, extracts bounded fields, and narrates verified JSON. The math, issue keys, owners, SQL templates, and write decisions are validated by code.

## Links
- Repo: https://github.com/bichtram-0701/claw-a-thon-team-uw
- Live agent: https://endpoint-2f37c067-4516-4483-ba07-2199f07abb90.agentbase-runtime.aiplatform.vngcloud.vn/
- Demo video: _add after recording_

## Submission checklist
- [ ] Remove `.env` and tokens from any shared ZIP.
- [ ] Rotate any token that was previously shared.
- [ ] Re-seed synthetic Atlassian workspace if needed.
- [ ] Set `ALLOW_WRITES=true` only for the demo workspace.
- [ ] Run `python tests/test_offline.py`.
- [ ] Verify `daily volume` and `day over day in May` route to analyst, and `draft my standup` routes to standup.
- [ ] Verify May daily totals reconcile to Traffic 800 -> Submission 216 -> Approval 24 -> Disbursement 23.
- [ ] Verify `/confluence weekly meeting summary` drafts a meeting readout.
- [ ] Verify Confluence publishing only when writes are intentionally enabled.
