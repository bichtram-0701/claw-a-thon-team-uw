# Use-case description

## Short description (for the submission form — must be ≤ 300 characters)

> An AI agent for the Data Analysis track. It auto-retrieves funnel data,
> computes conversion and drop-off at each stage (deterministically), then uses
> Gemma/Qwen via MaaS to synthesize an executive report with ranked, numbers-backed
> recommendations. Synthetic data only.

Character count: **269** (within the 300-char limit). Paste this into the
"Use case description" field; it states the problem, the user, and how the agent
solves it — no placeholder/lorem-ipsum.

## Extended description

**Problem.** Conversion-funnel analysis is repetitive and manual — pull data,
compute step conversion, find the biggest drop-off, slice by segment, write it
up. Hours of analyst time, done inconsistently.

**User.** Growth / product / ops analysts who own a conversion funnel (signup,
checkout, onboarding, loan application, etc.).

**How the agent solves it.** In one call it (1) retrieves the funnel CSV,
(2) computes stage counts, step conversion, drop-off, stage velocity and segment
breakdowns deterministically, self-verifying the math, and (3) sends the verified
metrics to a MaaS model (Gemma/Qwen) to produce an executive summary and 3–5
prioritised, quantified recommendations.

**Value.** Minutes instead of hours; consistent, trustworthy reporting (numbers
are computed, not hallucinated); the highest-impact leak is surfaced
automatically.
