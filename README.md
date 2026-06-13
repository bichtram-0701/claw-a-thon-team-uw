# Funnel Watchtower

> Claw-a-thon 2026 — **Team UW** — Track: **Agentic Assistant**

A line-manager oversight agent for the **lending application funnel**. Every
initiative that moves a funnel metric — reduce docs-upload drop-off, lift
approval rate, cut disbursement abandonment — lives in Jira with an owner, a
stage, a due date, and a criticality. Funnel Watchtower reads it all and answers,
in plain language (Vietnamese or English): **who is working on what, what's on
track, and what's critical right now.** Deterministic clients fetch the facts;
the MaaS LLM only narrates, so it never invents an initiative, owner, or number,
and every feature degrades gracefully when Jira, Confluence, or the LLM is down.

**💬 Try it in your browser (no install):**
https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/

## Problem

A lending lead's morning is spent reconstructing the funnel program by hand:
which conversion initiatives are in flight, who owns each, what's slipping, and
what's critical — scattered across Jira boards and Confluence pages. Deterioration
and blockers surface late, after a stage metric has already dropped.

## User

The **lending team lead / line manager** running the funnel-improvement program
(primary), and the contributors who each own initiatives (secondary).

## Solution

Ask in plain language (Vietnamese or English) — the agent:

1. **Funnel oversight (the LM view)** — "give me the funnel overview" / "what's
   critical or off track?": leads with *needs-attention-now* (critical **and**
   overdue/blocked), then a read per funnel stage, flagging overloaded owners.
2. **Ownership** — "who is working on what?": initiative load per owner, with
   how many of theirs are critical or off track.
3. **Knowledge lookup** — "what did we decide about docs-upload?": searches
   Confluence, answers from the page, cites title + link.
4. **My plate** — a contributor's own ranked initiatives (overdue/blocked first).
5. **Standup draft** — a ready-to-paste Yesterday / Today / Blockers message.
6. **Daily LM digest** — a scheduled GitHub Action calls the agent each weekday
   morning and posts the oversight read to the run summary (the "reminder").
7. **Web chat UI** — served by the agent at the endpoint root; EN & VI.

## Value

The lead's morning tab-hop becomes one question. Critical-and-slipping work is
surfaced first, the moment it's asked — or pushed automatically each morning.
Ownership and stage health are visible at a glance, and every figure is real
(from a deterministic Jira/Confluence call) rather than model-invented.

## Try it (live)

Deployed endpoint: https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn

```bash
curl -X POST https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/invocations -H 'Content-Type: application/json' \
  -d '{"message": "what is critical or off track right now?"}'

curl -X POST https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/invocations -H 'Content-Type: application/json' \
  -d '{"message": "ai dang lam gi, co gi tre khong?", "language": "vi"}'
```

Run locally: `pip install -r requirements.txt && python main.py` (port 8080).
Offline tests (no network/credentials needed): `python tests/test_offline.py`.

## Demo video

🎬 _[link — to be added]_

## Architecture & design

```
User ─▶ Agent (AgentBase, MaaS model: Qwen/Gemma)
            │
            ├── intent router (keywords first, LLM classify on miss)
            ├── jira_client.py        → Jira Cloud REST v3  (funnel initiatives)
            ├── confluence_client.py  → Confluence Cloud v2 (decisions / charters)
            ├── briefing.py           → deterministic shaping; manager_digest() is
            │                           the LM centerpiece (who/on-track/critical/stage)
            └── report.llm_chat       → LLM narration + offline fallback
```

Key choice: **deterministic clients compute every fact; the LLM only phrases
it.** Ownership and funnel stage are encoded as Jira labels (`owner-<name>`,
`stage-<applied|docs|approved|disbursed|crosscut>`) because the free workspace
has a single real user; priority encodes criticality and the due date is the
on-track signal. The agent never returns a number or key the data didn't contain,
and if MaaS is down it falls back to the structured JSON.

## Daily LM digest (the reminder)

`.github/workflows/lm-digest.yml` runs on a weekday-morning cron, calls the live
agent for its oversight read, and writes the digest to the workflow run summary.
It uses GitHub's runners because our dev sandbox can't reach vngcloud.vn — the
same pattern as deploy/seed/debug. To deliver it to email/Slack/Teams, add a
step after "Compose".

## Models & resources

- GreenNode MaaS (competition tokens): Qwen / Gemma, auto-discovered at runtime
  (the client self-heals if a configured model name 404s)
- Atlassian: a **free** Atlassian Cloud workspace (personal API token), seeded
  with synthetic funnel initiatives — no company systems, no real personal data
- Deploy pipeline: GitHub Actions → AgentBase Container Registry → Agent Runtime
  (endpoints from the BTC's [greennode-agentbase-skills](https://github.com/vngcloud/greennode-agentbase-skills) pack)
- No external paid models used

## Data

100% synthetic. `scripts/seed_atlassian.py` (run via the *Seed Atlassian
workspace* Action, with `reset` to replace) populates ~20 funnel initiatives
across the stages applied → docs → approved → disbursed plus cross-cutting work,
each with an owner, due date, criticality and status, and six Confluence pages
(funnel charter, decision log, sprint planning, an incident postmortem, metric
definitions, working agreements). No real people, tickets, or data.

> Note: the company Jira is internal and is **not** used in the competition
> (network, security, and data rules). The same code can later point at an
> internal workspace with service-owner approval — only env vars change.

## Repo notes

The team's earlier entry, *Lending Portfolio Watchdog* (Data Analysis track),
lives on in git history; this agent reuses its deploy pipeline, chat UI, and
LLM brain (routing, narration, anti-hallucination, graceful fallback), and keeps
the lending-funnel domain at its center.

## Team

| Member | Department |
|--------|-----------|
| Hathy (Tramctb2) | Credit Risk |
| Rino (rinotrann) | _[dept]_ |
