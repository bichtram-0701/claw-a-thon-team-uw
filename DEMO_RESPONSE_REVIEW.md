# Demo response review and fixes

This note reviews issues found in the exported chatbot/Confluence demo response and what was fixed.

## 1. Confluence rendered raw Markdown

Observed issue:

- Confluence showed text such as `**Date:**`, `**Approval**`, and `* **Signal:**` literally.
- Bullet formatting looked odd because the storage converter only recognized `-` bullets, while the LLM often emitted `*` bullets.

Root cause:

- `confluence_client.markdown_to_storage()` escaped entire paragraph/list lines but did not convert inline Markdown such as bold, italic, code, or links.
- It also did not support numbered lists or `*` bullets.

Fix:

- Added a safer Markdown-to-Confluence storage converter for headings, paragraphs, bold, italic, inline code, links, `-` bullets, `*` bullets, numbered lists, fenced code, and Markdown tables.
- Weekly pages should now render normal Confluence formatting instead of raw `**...**` markers.

## 2. Weekly summaries were too LLM-dependent

Observed issue:

- The weekly prompt produced inconsistent formatting and could rephrase operational facts differently across runs.

Fix:

- Weekly meeting notes now use the deterministic `briefing.render_weekly_summary()` as the canonical artifact.
- The LLM is no longer needed to produce the Confluence page body, so issue counts, value-at-risk wording, and sections stay stable.

## 3. Old UI copy was still lending/Vietnamese-oriented

Observed issue:

- The saved HTML still said `loan funnel`, `Disbursement`, `EN & VI`, and included a Vietnamese suggestion.

Fix:

- Chat UI now describes a generic demo funnel: `Traffic -> Submission -> Approval -> Completion`.
- Removed Vietnamese from the visible suggestions and UI copy for this submission.
- Vietnamese fallback routing may still exist in code, but the demo no longer optimizes or advertises it.

## 4. Old drop-reason response did not reconcile

Observed issue:

- The old `break May down by drop reason` response counted all May rows and included completed rows as blank drop reasons.
- It did not answer the actual question: where did submitted-but-not-approved users/entities drop?

Fix:

- The analyst template now scopes this prompt to `drop_transition = 'submission_to_approval'` by default.
- For May 2026, it should reconcile:
  - Submitted: 216
  - Approved: 24
  - Submission -> Approval drop: 192
  - Drop-reason rows sum to 192.

## 5. Old runtime/data was stale

Observed issue:

- The export showed the previous runtime/version and old monthly totals such as 10,500 May traffic.

Fix:

- Current demo data is row-level and smaller: 4,650 rows total across six months.
- May 2026 now reconciles to `Traffic 800 -> Submission 216 -> Approval 24 -> Completion 23`.
- Daily and monthly metrics aggregate from the same CSV source of truth.

## v6 review: Jira links + UW project JQL scoping

Observed in saved runtime export:
- `flag the drops and assign owners to investigate` created `UW-159` and `UW-160`, but the answer only showed bare issue keys rather than clickable links.
- Follow-up Jira/Confluence paths (`what is critical or off track right now?`, `what does blocked mean here...`, `weekly meeting summary`, `publish weekly...`) returned the generic error message.
- The metrics response also showed `Unassigned` / `no blocked/overdue work detected`, which indicated broad Jira reads were failing and being swallowed by the metrics fallback.

Root cause:
- After switching the Jira project key to `UW`, `_scope_jql()` wrapped the whole JQL string, including `ORDER BY`, inside parentheses. That produced invalid JQL such as:
  `project = "UW" AND (statusCategory != Done ORDER BY due ASC)`.
- Because broad Jira reads failed, oversight/weekly threw errors, metrics lost owner/execution-risk context, and investigation dedupe could not find existing open investigations.
- The flag handler only printed bare keys (`UW-159`) while the create handler appended a URL, so flag-created investigations did not look clickable in chat.

Fix:
- `_scope_jql()` now splits out `ORDER BY` and emits valid scoped JQL: `project = "UW" AND (statusCategory != Done) ORDER BY due ASC`.
- Added regression tests for JQL scoping with `ORDER BY`.
- Added Markdown linkification for bare Jira keys in successful bot answers, while avoiding keys already inside URLs or Markdown links.

## v7 review: demo order + explicit month comparison

Observed in saved runtime export:
- The conversation transcript mixed real demo steps with debugging/exploratory prompts such as `break April down by drop reason`, `how to use this chat`, repeated `weekly meeting summary`, and a later `can you do MoM comparison between March and April...`.
- The visible chip order put the long daily-volume table before the execution-context and weekly-readout steps.
- The explicit March/April comparison prompt routed to the generic latest-month metrics answer and incorrectly answered with the May risk ranking.

Fix:
- Reordered the chat suggestions around the main narrative: detect -> diagnose -> execution context -> blocked semantics -> act -> weekly readout -> optional Confluence publish.
- Moved `show daily volume in May` to the backup validation area because it returns a long 31-row table and is not necessary for the 2-3 minute pitch.
- Added explicit month-comparison handling for prompts such as `compare April and May performance`; those now answer the requested months instead of defaulting to the latest May view.
- Updated `DEMO_PROMPTS.md`, `HOW_TO_USE_WATCHTOWER.md`, `PITCH.md`, and `SUBMISSION.md` to match the new demo order.
