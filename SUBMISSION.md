# Submission form drafts — Team UW (copy-paste on submission day)

> Form fields per training slides: Agent name · Tagline · Problem · Solution ·
> Value · Voter guide · Links. Use case description: 100–200 words (user guide).
> Form opens after Training Day, editable until 17/06 12:00. Submit EARLY (16/06 evening).

## Agent name
Funnel Watchtower

## Tagline
The lending lead's morning oversight — who owns each funnel initiative, what's on
track, and what's critical right now, in plain language.

## Track
Agentic Assistant

## Problem
A lending lead's morning is spent reconstructing the funnel program by hand:
which conversion initiatives are in flight (reduce docs-upload drop-off, lift
approval rate, cut disbursement abandonment), who owns each, what's slipping, and
what's critical — scattered across Jira boards and Confluence pages. Blockers and
deterioration surface late, after a stage metric has already dropped.

## Solution
A bilingual (VI/EN) AI agent on GreenNode AgentBase, connected to Jira +
Confluence, built for line-manager oversight of the loan-application funnel. Ask
"what's critical or off track?", "who is working on what?", "what did we decide
about docs-upload?" and get analyst-grade answers with real issue keys and owners.
It leads with what needs attention now (critical AND overdue/blocked), reads each
funnel stage, and a scheduled job pushes the digest every morning. Deterministic
clients compute every fact; the MaaS LLM (Qwen) only narrates — so it never
invents an initiative or number, and every feature has an offline fallback.

## Value
The lead's morning tab-hop becomes one question — or an automatic daily digest.
Critical-and-slipping work is surfaced first, the moment it's asked. Ownership
and stage health are visible at a glance, and every figure is real (from a Jira/
Confluence call) rather than model-invented. A web chat means anyone can use it
with zero setup.

## Voter guide (how to try it)
Open the link, no install needed:
https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/
Click a suggestion chip or ask your own question — English or Vietnamese:
- "give me the funnel overview"
- "what's critical or off track?"
- "who is working on what?"
- "what did we decide about docs-upload?"
- "ai dang lam gi, co gi tre khong?"
All data is in a synthetic workspace — no company systems, no real personal data.

## Use case description (100–200 words; current count ≈ 155)
A lending team lead running the application-funnel improvement program loses time
every morning reconstructing it by hand: which initiatives are in flight, who
owns each, what's blocked, what's critical — spread across Jira and Confluence.
Problems surface after a stage metric has already dropped.

Funnel Watchtower is an AI agent on GreenNode AgentBase, connected to Jira and
Confluence, built for that oversight. In Vietnamese or English — "what's critical
or off track?", "who is working on what?", "what did we decide about docs-upload?"
— it answers with concrete issue keys and owners, because deterministic clients
fetch every fact and the MaaS LLM (Qwen) only narrates. It leads with what needs
attention now (critical AND overdue/blocked), reads each funnel stage, flags
overloaded owners, and a scheduled job pushes the digest each morning. A built-in
web chat means anyone can use it with zero setup. All demo data is synthetic.

## Links
- Repo (PUBLIC through 03/07): https://github.com/bichtram-0701/claw-a-thon-team-uw
- Live agent + web chat (optional endpoint field):
  https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/
- Demo video: _[add after recording — YouTube unlisted or OneDrive shared to @vng.com.vn]_

## Submission-day checklist
- [ ] Repo public, README filled (name, description, how to run) ✓ already
- [ ] Agent ACTIVE on AgentBase (BTC will call it at least once)
- [ ] Workspace re-seeded with funnel initiatives + token still valid (re-run Verify if unsure)
- [ ] Redeploy AFTER secrets valid so the runtime has Atlassian env vars
- [ ] Video viewable from a @vng.com.vn account
- [ ] Wallet has credit (runtime keeps burning through voting — check portal)
- [ ] Keep everything running + public until voting closes 03/07 11:00
