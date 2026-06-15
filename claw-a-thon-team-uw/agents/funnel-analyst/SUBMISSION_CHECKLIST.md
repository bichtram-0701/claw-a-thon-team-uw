# Submission checklist — Claw-a-thon 2026

**Deadline: 12:00, 17/06/2026** (form closes; repo state is frozen at that moment).

## PASS criteria (all 3 must be true simultaneously)

- [ ] **1. Deployed & running on AgentBase**, BTC can open the link and call it
      ≥ 1 time. → Wrap `src.agent.run` with the BTC AgentBase template and deploy.
- [ ] **2. Running in the correct registered category** → **Data Analysis**
      (agent does retrieve → analyze → synthesize → report).
- [ ] **3. Full use-case description** → `README.md` (problem/user/solution) +
      ≤300-char form text from `USE_CASE.md` (real content, no placeholder).

## Required form fields

- [ ] **Team name** — unique, ≤ 60 chars.
- [ ] **Track** — Data Analysis.
- [ ] **AgentBase project link (GitHub)** — public or internal; agent running on
      AgentBase at submission time.
- [ ] **Demo video** — 2–3 min, YouTube or OneDrive (shared in VNG domain),
      showing the agent run end-to-end on 1 use case (suggested script below).
- [ ] **Use-case description** — paste the ≤300-char text from `USE_CASE.md`.
- [ ] **Department + members' names** — 1–3 members, @vng.com.vn emails.

## Pre-submission verification

- [ ] `python run.py --out report.md` runs clean; `[verify] passed=True`.
- [ ] Real MaaS key set; `[llm] used=True` and a full narrative is produced.
- [ ] AI-disclosure banner present at top of the report.
- [ ] Only synthetic data committed; `.env` is git-ignored (no key leaked).
- [ ] README states problem/user/solution and model used.

## Suggested 2–3 min demo video script

1. (0:00–0:20) State the problem: manual funnel analysis is slow/inconsistent.
2. (0:20–0:40) Show the synthetic input CSV and `config.json` stages.
3. (0:40–1:40) Run the agent on AgentBase; show it compute the funnel and the
   AI write the executive summary + recommendations. Point out the biggest leak.
4. (1:40–2:20) Re-run on a different synthetic file / segment to show it's
   general-purpose. Show the AI-disclosure banner and that numbers are verified.
5. (2:20–2:45) Recap value: minutes vs hours, trustworthy numbers, MaaS-powered.

## Support routing (if blocked)

- Rules / criteria → Teams BTC support (PIC for your group), ~3–4h SLA.
- Technical (account, AgentBase, API, deploy) → Teams BTC support → ENG team.
- Office 365 tool access → helpdesk@vng.com.vn, 8h SLA (personal resources only).
- Report any technical submission error to BTC **before 12:00 17/06** to be valid.
