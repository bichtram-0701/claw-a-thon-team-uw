# Submission form drafts — Team UW (copy-paste on submission day)

> Form fields per training slides: Agent name · Tagline · Problem · Solution ·
> Value · Voter guide · Links. Use case description: 100–200 words (user guide).
> Form opens after Training Day, editable until 17/06 12:00. Submit EARLY (16/06 evening).

## Agent name
Lending Portfolio Watchdog

## Tagline
Your loan book's early-warning system — ask anything, catch risk before it becomes NPL.

## Track
Data Analysis

## Problem
Lending teams monitor portfolio health by hand: exporting data, rebuilding the
same overdue/NPL pivots every week, and eyeballing for risky accounts. Segment
deterioration is usually spotted weeks late — after loans have already rolled
into NPL — and funnel problems (where applications drop off) live in yet another
manual report.

## Solution
A bilingual (VI/EN) AI agent on GreenNode AgentBase: ask portfolio or funnel
questions in plain language and get analyst-grade answers with real numbers; it
auto-flags accounts days away from the 90-DPD cliff, explains application
drop-off by product and channel, and writes manager-ready markdown reports.
Deterministic Python computes every number; MaaS Qwen narrates — so it never
invents figures, and every LLM feature has an offline fallback.

## Value
Hours of weekly manual reporting → minutes. Deterioration caught before NPL,
not after. Funnel leaks visible the day they start. One consistent set of
metrics for the whole team — and a web chat anyone can use with zero setup.

## Voter guide (how to try it)
Open the link, no install needed:
https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/
Click a suggestion chip or ask your own question — English or Vietnamese:
- "which accounts are at risk?"
- "show me the application funnel"
- "give me a table of stage counts per product"
- "cho tôi báo cáo tuần"
All data is synthetic — no real customer information.

## Use case description (100–200 words; current count ≈ 150)
Lending teams at consumer-finance companies track portfolio health manually:
exporting loan tapes, rebuilding the same overdue and NPL pivot tables every
week, and scanning by eye for risky accounts. Deterioration in a segment is
typically discovered weeks late, after loans have already rolled into NPL, and
application-funnel problems are tracked in yet another manual report.

Lending Portfolio Watchdog is an AI agent on GreenNode AgentBase that gives the
whole team instant visibility. Analysts ask questions in Vietnamese or English —
"which accounts are at risk?", "why are applications dropping off?" — and get
analyst-grade answers with concrete numbers, because deterministic Python
computes every metric and the MaaS LLM (Qwen) only narrates. The watchdog
auto-flags loans days before they become NPL, funnel analytics show where
applications leak by product and channel, and one-click reports produce
manager-ready reviews. A built-in web chat means anyone — from analyst to
CEO — can use it from a browser with zero setup. All demo data is synthetic.

## Links
- Repo (PUBLIC through 03/07): https://github.com/bichtram-0701/claw-a-thon-team-uw
- Live agent + web chat (optional endpoint field):
  https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/
- Demo video: _[add after recording — YouTube unlisted or OneDrive shared to @vng.com.vn]_

## Submission-day checklist
- [ ] Repo public, README filled (name, description, how to run) ✓ already
- [ ] Agent ACTIVE on AgentBase (BTC will call it at least once)
- [ ] Video viewable from a @vng.com.vn account
- [ ] Wallet has credit (runtime keeps burning through voting — check portal)
- [ ] Keep everything running + public until voting closes 03/07 11:00
