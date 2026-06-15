# PIVOT PROPOSAL — from "Lending Portfolio Watchdog" to "Sprint Sidekick"
### For team discussion — nothing is shelved until all three of us agree.

## Why pivot (Rino's case)
The data-analysis agent demos well, but it solves a problem that general AI
tools (Claude/ChatGPT + a CSV) already solve better ad-hoc. It isn't something
we would open every morning. The daily pain we actually have: tasks scattered
across Jira, decisions buried in Confluence, and "what should I focus on
today?" answered by 20 minutes of tab-hopping.

## The new agent — Sprint Sidekick
A briefing agent connected to Jira + Confluence (free Atlassian Cloud,
synthetic project data for the competition):

1. **Morning briefing** — "what's on my plate?": my open issues ranked by due
   date/priority, blockers, what changed overnight.
2. **Team pulse** — "how is the sprint going?": burndown-style summary, stuck
   tickets (no update > N days), who's overloaded.
3. **Knowledge lookup** — "what did we decide about X?": searches Confluence
   pages, answers with the decision + link.
4. **Standup draft** — writes my yesterday/today/blockers from actual ticket
   activity.
- Same web chat UI; bilingual VI/EN; track likely "Agentic Assistant" (TBC).

## What we KEEP (≈70% of the work)
- GitHub Actions deploy pipeline with version verification — unchanged
- Web chat page (chat.html) — re-skinned texts only
- LLM brain (report.py): routing, narration, fallbacks, anti-hallucination — unchanged pattern
- Debug workflow, runtime, endpoint, repo — unchanged

## What we REPLACE
- metrics.py/funnel.py (lending analytics) → jira_client.py + confluence_client.py + briefing.py
- Synthetic loans/applications → synthetic sprint (tickets, comments, pages)
- README + submission texts (drafted by Claude, reviewed by team)

## What we LOSE (honest column)
- Hathy's metrics/report engine goes dormant (stays in git history + could be
  cited as "phase 1" in the story)
- The reconciled lending data story
- ~1 day of polish already invested in lending-specific demo lines

## Constraints checked
- Free Atlassian Cloud: 10 users, full REST API, personal token — no approvals needed
- Company Jira (jira.zalopay.vn) is internal — NOT used in competition (network +
  security + data rules). Post-competition work version: same code, internal deploy,
  service-owner approval.
- Synthetic data only; public endpoint stays safe (token only reads our fake workspace)
- Sandbox can't reach Atlassian — seeding/verification runs via GitHub Actions

## Timeline (deadline 17/06 12:00, target submit 16/06 evening)
- **12/06 (tonight):** team decision · create Jira project + Confluence space (UI)
  · add 3 GitHub secrets · run Verify workflow
- **13/06:** Claude builds clients + intents + briefing logic; seed workflow
  populates synthetic sprint; local mock tests
- **14/06:** deploy, end-to-end testing (the Rino adversarial special), fix round
- **15/06:** polish answers, README + submission texts final, record video
- **16/06:** buffer + submit
- **Fallback:** lending agent stays deployed & submittable until the moment the
  new one passes end-to-end tests. We can abort the pivot any day and lose nothing.

## Team asks
- Hathy: bless the pivot (or argue!) · own prompt quality + test questions again
- Member 3: video script + recording on 15/06 · submission form owner
- Rino: workspace admin, secrets, testing, demo
