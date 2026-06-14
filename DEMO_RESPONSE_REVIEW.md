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

## v9 review: UI version + answer bugs from v8 export

Observed in the v8 saved chatbot export:
- The page itself did not show a visible UI/build version, only each bot response returned a backend hash such as `v7a1b54c`.
- `break May approval drop down by reason` routed to the diagnostic contribution table instead of the drop-reason reconciliation table.
- `what does blocked mean here and what is it blocking?` routed to the help/usage guide instead of the Jira blocker explanation.
- The welcome text said the last two chips were for month comparison and usage guidance, but the chip order had more optional prompts at the end.
- Weekly meeting context could include previously generated Watchtower weekly summary pages, causing recursive/noisy Confluence context.

Fix:
- Added a visible `UI v11` badge in the chat header and footer. The backend/agent version still appears in each response meta line.
- Added a router guard so blocker-semantics prompts route to `oversight`, not `help`.
- Added SQL-template matching for `by reason` / `down by reason`, so `break May approval drop down by reason` uses `approval_drop_reason_breakdown` and reconciles the 192 submitted-but-not-approved rows.
- Updated the intro copy to say optional prompts cover Teams, MoM comparison, daily validation, and usage guidance.
- Strengthened Confluence context filtering to exclude self-generated Watchtower weekly summary pages from future weekly briefs.

## v9 review fixes

Observed in the v8 saved chat export:

- `break May approval drop down by reason` routed to the diagnostic contribution template instead of the drop-reason reconciliation table. Fixed by recognizing `down by reason` / `by reason` phrasing as a drop-reason request and routing it to `approval_drop_reason_breakdown`.
- `what does blocked mean here and what is it blocking?` sometimes routed to the generic help guide. Fixed with an explicit blocker-follow-up guard that routes this prompt to the Jira oversight context.
- Weekly summaries could include a previously generated Watchtower weekly page as Confluence context, creating recursive/noisy context. Fixed by filtering self-generated weekly summary/readout pages from Confluence context.
- The chat page did not make the UI/demo version visible enough. Added `UI v11` in the header/footer while keeping the served agent build hash in each response meta and the `/version` endpoint.

## v10 review: unassigned task follow-up

Observed issue: when the user asked `what are those 9 open tasks without assignee`, the answer said the JSON only contained an aggregate `by_owner.Unassigned` count and could not list the individual issue keys. That was not the desired behavior for a manager follow-up.

Fix:
- `manager_digest()` now includes `owner_unassigned_open` and `assignee_unassigned_open` detail lists, not only aggregate counts.
- Router now treats `unassigned`, `without assignee`, `no assignee`, `without owner`, and similar phrases as `oversight` prompts.
- Added a deterministic renderer for unassigned-work questions so the bot lists issue keys, summaries, stage, status, due date, owner, and assignee instead of asking the LLM to infer from aggregate JSON.
- Added regression coverage for the route and renderer.

## v10 saved-chat review -> v11 fixes

Observed in `Funnel Watchtower - Team UW_v10(1).html`:

1. `show me the funnel metrics in April` still answered with the latest May recovery priority and showed May as the latest month. Fixed by adding month-scoped metrics rendering and MoM cut-off tables.
2. `can you cutoff May and show what's recovery priority in April?` still answered with May Approval risk. Fixed by treating the final named month as the requested as-of month for non-comparison metrics/risk prompts.
3. `I'd like to investigate traffic drop in May also, create a ticket for this` routed to analyst SQL instead of Jira creation. Fixed by adding an explicit create-ticket routing guard before analyst/flag handling.
4. `how do I query the database?` returned the generic usage guide. Fixed by adding a database/schema guide for `funnel`, columns, counting rules, and safe SQL behavior.
5. `who's the owner of each epic?` answered only with raw Jira Epic assignee data, making all Epics look unowned. Fixed by returning both semantics: Jira Epic assignee can be unassigned, while Watchtower's operational stage owner is inferred from open work owner labels/assignees.

## v11 saved-chat review -> v12 reliability layer

The remaining class of issues was not one specific answer; it was ambiguity in mapping user language to workflows. v12 adds a command-prefix layer:

- `metrics:` for funnel metrics, MoM, top risk, and value at risk.
- `sql:` for deterministic DuckDB templates and drilldowns.
- `jira:` for ownership, blockers, off-track work, and Jira write actions.
- `confluence:` for weekly summaries and Confluence publishing.
- `teams:` for Teams reminders.
- `help:` for usage/database guidance.

In `ROUTING_MODE=warn`, non-prefixed read-only prompts still answer but include a routing warning. Non-prefixed write actions are blocked and ask the user to resend with the explicit prefix. Ambiguous prompts such as `why did it drop?` ask for clarification instead of guessing the stage or transition.
