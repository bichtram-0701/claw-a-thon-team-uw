# Funnel Watchtower — Why this, not a general chatbot

> Demo script + objection handling for Claw-a-thon 2026, Team UW.
> One idea runs through it: **the bottleneck was never intelligence — it's a
> trustworthy, ready-made way of working, wired into our funnel and our team.**

## Lead with the method, not the tech

Funnel Watchtower is our **actual team workflow, running itself**. Not a generic
project bot — the opinionated way a credit-risk data team already works, made
effortless:

- **Epics = the funnel** (Traffic → Submission → Approval → Disbursement) plus a
  Data & Platform Epic. Each Epic has one owner.
- **Tasks = the work**, with just two things that matter: a **name** and a **due
  date**. Owner defaults to you. That's it — simple enough for anyone to follow.
- **Reminders** keep it honest: overdue, due-soon, and stale work get pushed to
  the team automatically.

This is the real moat. Methodology is hard to copy, and the agent's answers are
only meaningful *because* the workflow underneath is clean. We're not selling a
chatbot; we're selling a proven operating rhythm that maintains itself.

**And it runs on the exact tools we already use — Jira, Teams, Confluence.** No
new app, no migration, no behavior change. The agent meets the team where the
work already happens, so the friction to adopt is as close to zero as it gets.
Low friction in the method *and* the tooling.

## The bottleneck (the "Why")

A lending lead's morning: "How's the funnel? What's slipping? Who owns it? What
do we do?" The answers live in five places — Jira, Confluence, CSV exports,
dashboards, Teams. So it's 20 minutes of tab-hopping daily, the same pivots
rebuilt weekly, and deterioration spotted **weeks late**. The bottleneck isn't
that nobody can reason about the funnel — it's that the reasoning isn't
connected to the data, the board, the team, or the ability to act.

## Why the funnel (and why it's not niche)

The funnel isn't an arbitrary demo topic — it's the best fit for what this agent
*does*. The engine is "a number moved the wrong way → which part owns it → assign
that owner → notify." That loop needs an **attributable, structured metric**, and
a funnel delivers exactly that: sequential stages, a conversion rate between each,
and one owner per stage. When approval drops, there's an obvious person to flag.

The funnel already carries the headline volume number too — disbursement count and
**amount** (the VND row) and avg ticket size — and because it's a funnel, that
number already has an owner. A standalone KPI can't say who's responsible; the
funnel can.

**Layer OKR targets on top and every metric becomes goal-aware.** Add a target per
metric and the agent reports *actual vs target* ("disbursement is 4.0B, 12% behind
June's target"), and the flag engine gains a second trigger: not only "dropped
month-over-month" but "**behind / at risk of missing target**" — routed to the same
stage owner. This maps straight to the real board (the "will we reach 635B in June?"
question is an OKR), and OKRs are even more universal than funnels.

Frame it as the **flagship example of a universal pattern, not the whole product**:

> Every end-to-end product at ZaloPay has a funnel — lending, payments onboarding
> (KYC → first transaction), merchant acquisition, BNPL, wallet activation. And
> the same engine works for *any owned metric*, not just funnels.

That keeps the vivid, attributable demo while answering "isn't this niche?".

## "Couldn't you just use Claude or ChatGPT?" (the honest answer)

Yes — you can connect Claude or ChatGPT to Jira/Confluence today (connectors,
GPT actions, Atlassian Rovo). So "a general model can't connect or act" is **not**
our claim. What a general assistant does *not* give a regulated funnel team:

1. **Numbers you can trust and reproduce.** Watchtower computes funnel
   conversion, month-over-month drops, and by-stage ownership **deterministically
   in code** — same question, same audited number, every time, with the source.
   A general model reasoning over your data drifts run-to-run; for risk reporting,
   reproducibility beats cleverness.
2. **A proven workflow, zero setup.** A connector still needs wiring, prompt
   skill, and a definition of "off track," and gives variable output. Here a
   non-technical lead gets analyst-grade answers from one link, bilingual (VI/EN),
   with no prompting.
3. **It acts and pushes, in the tool the team lives in.** Detect a drop → open an
   investigation under the right Epic → assign the stage owner → notify them in
   **Teams**, on a schedule, without anyone asking. That proactive layer is built,
   not assumed.
4. **It runs on our own approved stack.** GreenNode MaaS keeps data in-tenant —
   which matters for in-country financial-data rules — at zero external cost.

Honest framing: parts of this *could* be assembled on a general agent. The value
is the **verticalization + determinism + workflow + governance + packaging**, not
impossibility. We pitch it as that.

## "Why MaaS and not the Claude model?"

Be straight about this — a judge will ask.

- **GreenNode MaaS** serves open models (Qwen/Gemma) on VNG's own infra: data
  stays in-tenant, it's the required competition stack, tokens are free/internal.
- **Claude** is a stronger frontier model (better reasoning, multilingual, code/SQL)
  but an external, paid service unless contracted in-region.

The key insight: **the model is a swappable engine, not the product.**

- Our numbers come from deterministic Python/SQL, **not** the model — so even Qwen
  returns correct figures. A stronger model would only narrate better and write
  better queries; it would not change whether "11%" is right.
- The agent auto-discovers its model from an env variable, so pointing it at
  enterprise Claude later is essentially a **one-line config change**.
- This also answers "use Claude/ChatGPT for the reasoning": go ahead — the agent
  deterministically *finds and localizes* the problem; the *why/what-to-do* reasoning
  is the swappable engine's job, and you can point it at whatever model you trust.

So: we build and demo on MaaS (required, free, in-country, and it proves the
numbers don't need a frontier model). If the org standardizes on enterprise Claude
later, Watchtower runs on it tomorrow — **the engine is swappable by design.**

## Live demo flow (4–5 min)

1. **Show the pain** (10s): a slide of scattered tabs — Jira, Confluence, a CSV.
2. **"Show me the funnel metrics"** → the monthly table; it **flags May's approval
   drop (15%→11%) and names the owner**.
3. **"Flag it"** → opens an investigation under the Approval Epic, **assigned to
   that owner**.
4. **Cut to Teams** → the notification card appears; the owner is pinged. Mention
   the morning overdue/stale digest also runs automatically.
5. **"Who's working on what / what's off track?"** → oversight grouped by Epic.
6. *(If SQL analyst is added)* **"break May down by day / by drop reason"** → it
   writes the query and answers **with the SQL shown** — proof the numbers are real.
7. **Close**: detect → assign → notify, automatically, bilingual, on synthetic data,
   already deployed. *Hours of manual oversight → one question and an automatic
   morning push.*

## Judge-ready rebuttals

- **"Why not Rovo / a Claude connector?"** → "Great if you can put your data in
  them and trust a model to compute risk metrics on the fly. We run on our own MaaS
  stack with deterministic, auditable funnel math — compliance is satisfied and the
  numbers are identical every time."
- **"Isn't this just a Jira wrapper?"** → "The wrapper is the point: it encodes a
  proven funnel workflow — Epics as stages, one owner each, task + due date — and
  turns metric drift into an assigned, notified action."
- **"What's the real innovation?"** → "Closing the loop on our own infra: from a
  funnel number to the right person doing something about it, with no setup and no
  data leaving the building."
