# Funnel Watchtower

> Claw-a-thon 2026 — **Team UW** — Track: **Agentic Assistant**

A line-manager oversight agent for the **lending application funnel**
(Traffic → Submission → Approval → Disbursement). It answers, in plain language
(Vietnamese or English): **how is the funnel performing, who is working on what,
what's on track, and what's critical** — and it can **create and assign**
initiatives back into Jira. Deterministic clients fetch and compute every fact;
the MaaS LLM only narrates, so it never invents a number, ticket, or owner, and
every feature degrades gracefully when Jira, Confluence, or the LLM is down.

**💬 Try it in your browser (no install):**
https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/

## Problem

A lending lead's morning is spent reconstructing the funnel by hand: the latest
conversion numbers in one spreadsheet, and which improvement initiatives are in
flight, who owns each, and what's slipping spread across Jira and Confluence.
Problems surface after a stage metric has already dropped.

## User

The **lending team lead / line manager** running the funnel (primary), and the
contributors who each own initiatives (secondary).

## The funnel (4 stages)

| Stage | Definition |
|-------|------------|
| **Traffic** | Users who are eligible and enter the lending flow (eligible traffic only) |
| **Submission** | Users whose application is successfully submitted and received by the partner |
| **Approval** | Users who are approved by the partner |
| **Disbursement** | Users who receive any disbursed amount from the partner |

Conversion is measured between consecutive stages (Submission = Submission/Traffic,
Approval = Approval/Submission, Disbursement = Disbursement/Approval, E2E =
Disbursement/Traffic).

## Solution

Ask in plain language (VI/EN) — the agent:

1. **Funnel metrics** — "show me the funnel metrics": a monthly table of Traffic /
   Submission / Approval / Disbursement, disbursed amount, avg ticket size, and the
   conversion rates between stages, with a trend headline.
2. **Funnel oversight (LM view)** — "what's critical or off track?": leads with
   *needs-attention-now* (critical **and** overdue/blocked), then a read per stage,
   flagging overloaded owners.
3. **Ownership** — "who is working on what?": initiative load per owner.
4. **Create** — "create a ticket to improve submission rate": extracts a structured
   initiative and files it in Jira (stage/owner/priority/due), assigning a real user
   when one matches.
5. **Assign** — "assign KAN-23 to Mai": sets a real Jira assignee (and the owner label).
6. **Knowledge** — "what did we decide about submission?": answers from Confluence with a link.
7. **My plate / Standup** — a contributor's ranked items, or a paste-ready standup.
8. **Daily LM digest** — a scheduled GitHub Action posts the oversight read each weekday.
9. **Web chat UI** — served by the agent at the endpoint root; EN & VI.

## Value

Both halves of the lead's morning in one place: how the funnel is performing **and**
what's being done about it. Critical-and-slipping work surfaces first; ownership and
stage health are visible at a glance; new initiatives can be filed and assigned
conversationally. Every figure is real (computed, not model-invented).

## Try it (live)

Deployed endpoint: https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn

```bash
curl -X POST .../invocations -H 'Content-Type: application/json' -d '{"message": "show me the funnel metrics"}'
curl -X POST .../invocations -H 'Content-Type: application/json' -d '{"message": "what is critical or off track right now?"}'
curl -X POST .../invocations -H 'Content-Type: application/json' -d '{"message": "ai dang lam gi, co gi tre khong?", "language": "vi"}'
```

Run locally: `pip install -r requirements.txt && python main.py` (port 8080).
Offline tests (no network/credentials): `python tests/test_offline.py` (60 checks).

## Demo video

🎬 _[link — to be added]_

## Architecture & design

```
User ─▶ Agent (AgentBase, MaaS model: Qwen/Gemma)
            │
            ├── intent router (keywords first, LLM classify on miss)
            ├── funnel_metrics.py     → monthly conversion table (data/funnel_metrics.json)
            ├── jira_client.py        → Jira Cloud REST v3  (read + create/assign)
            ├── confluence_client.py  → Confluence Cloud v2 (decisions / definitions)
            ├── briefing.py           → manager_digest(): who/on-track/critical/by-stage
            └── report.llm_chat       → LLM narration + offline fallback
```

Deterministic clients compute every fact; the LLM only phrases it. Ownership and
funnel stage are Jira labels (`owner-<name>`, `stage-<traffic|submission|approval|
disbursement|crosscut>`) because the free workspace has few real users; priority
encodes criticality and the due date is the on-track signal. Writes are gated by
`ALLOW_WRITES` and assign to a real Jira user when one matches, else stamp the owner label.

## Daily LM digest (the reminder)

`.github/workflows/lm-digest.yml` runs on a weekday-morning cron, calls the live
agent for its oversight read, and writes the digest to the workflow run summary.
GitHub runners are used because the dev sandbox can't reach vngcloud.vn — same
pattern as deploy/seed/debug.

## Models & resources

- GreenNode MaaS (competition tokens): Qwen / Gemma, auto-discovered at runtime
- Atlassian: a **free** Atlassian Cloud workspace (personal API token), seeded with
  synthetic funnel initiatives + funnel metrics — no company systems, no real data
- Deploy: GitHub Actions → AgentBase Container Registry → Agent Runtime
- No external paid models used

## Data

100% synthetic. `scripts/seed_atlassian.py` (run via the *Seed Atlassian workspace*
Action, `reset` to replace) populates ~20 initiatives across Traffic / Submission /
Approval / Disbursement + cross-cutting, each with owner, due date, criticality and
status, plus Confluence pages (stage definitions, charter, decision log, metric
definitions, planning, postmortem, working agreements). `data/funnel_metrics.json`
holds a small 6-month synthetic performance series. The seed maps unsupported issue
types (e.g. Story) to ones the project accepts. No real people, tickets, or data.

> Note: company Jira is internal and **not** used in the competition. To assign to
> real people, invite teammates as users in the free Atlassian site (up to 10) —
> two underwriting users have already joined for the Approval stage.

## Repo notes

The team's earlier entry, *Lending Portfolio Watchdog* (Data Analysis track), lives
on in git history; this agent reuses its deploy pipeline, chat UI, and LLM brain.

## Team

| Member | Department |
|--------|-----------|
| Hathy (Tramctb2) | Credit Risk |
| Rino (rinotrann) | _[dept]_ |
