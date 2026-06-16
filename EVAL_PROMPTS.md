# Funnel Agent evaluation prompts

Use this file as a small regression set for LLM routing and answer quality.
The offline tests cover many of these as deterministic fallbacks; a live MaaS run
should also check route source, confidence, and final answer quality.

## Routing checks

| Prompt | Expected intent | Notes |
|---|---|---|
| show me the funnel metrics | metrics | Natural read-only funnel report; no routing warning |
| break May approval drop down by reason | analyst | Exact data-drilldown route |
| /jira flag the drops and assign owners to investigate | flag | Exact Jira write route |
| /jira what does blocked mean here and what is it blocking? | oversight | Blocker semantics, not generic help |
| weekly meeting summary | weekly | Natural read-only weekly pack |
| /confluence publish weekly meeting summary to Confluence | weekly | Confluence write route |
| /teams post off-track blockers | teams | Teams write route |
| /help how should I ask questions? | help | Usage guide |
| /model | model | Deterministic runtime/model info, not LLM self-identification |
| what was done in March to improve approval? | metrics | Historical Jira/Confluence evidence + outcome caveat |
| flag the drops and assign owners to investigate | flag + prefix_required | Non-slash-command write should be blocked in warn mode |
| show me the funnel metrics | metrics | Non-slash-command read-only answers naturally with no routing warning |
| why did it drop? | help + clarification_required | Ambiguous stage should ask clarification |

## Routing near-collisions

| Prompt | Expected intent | Notes |
|---|---|---|
| daily volume in May | analyst | Must not route to standup; natural read-only; no warning |
| can you give me the number day over day in May | analyst | Day-over-day wording should trigger daily template; natural read-only; no warning |
| show daily volume | analyst | Analytics request; natural read-only; no warning |
| draft my daily standup | standup | Standup keyword must win only with standup context |
| draft my standup | standup | Standard standup request |
| daily approval volume by channel | analyst | data-drilldown breakdown |
| weekly volume in May | analyst | Data aggregation, not weekly meeting |
| prepare weekly meeting summary | weekly | Meeting summary; natural read-only; no warning |
| publish weekly meeting summary to Confluence | weekly + prefix_required | Non-slash-command Confluence write should be blocked |
| show me the funnel metrics | metrics | Standard metric table; natural read-only; no warning |
| what is the approval rate? | metrics | Narrow metric question |
| what is critical or off track? | oversight | Manager digest; natural read-only; no warning |
| who is working on what? | oversight | Ownership / manager execution view |
| what is on my plate? | briefing | Contributor briefing |
| draft my standup | standup | Contributor update |
| what did we decide about submission? | knowledge | Confluence context |
| flag the approval drop | flag + prefix_required | Non-slash-command Jira write should be blocked |
| flag it | flag + prefix_required | Non-slash-command Jira write should be blocked |
| create a ticket to improve submission rate | create + prefix_required | Non-slash-command Jira write should be blocked |
| assign UW-23 to Mai | assign + prefix_required | Non-slash-command Jira write should be blocked |

## Answer-quality checks

For metrics answers:

- Must include actual computed rates from `funnel_metrics.py`.
- Must mention impact ranking when target misses exist.
- Must not invent owners or Jira issue keys.

For data-drilldown answers:

- Prefer `source=template` for supported breakdowns.
- `show daily volume in May` and `can you give me the number day over day in May` should return daily rows whose totals reconcile to monthly metrics.
- `break May approval drop down by reason` should explain the Submission -> Approval loss: May submitted 216, approved 24, stage drop 192.
- Show the SQL.
- Reject or avoid non-read SQL.

For Jira flagging:

- One open investigation per stage + metric + month.
- If an investigation exists, comment/update instead of creating a duplicate.
- Include an investigation contract in the description or comment.

For weekly summary:

- Include executive summary, impact-ranked risks, execution follow-up, Confluence
 context, and proposed agenda.
- If asked to publish and writes are disabled, clearly say it drafted but did not
 publish.

## Teams workflow checks

- New Jira task events should produce a Teams card with required fields.
- Task updates should show changed fields old value -> new value.
- The 09:00 digest should include overdue tasks and stale open tasks.
- The 17:00 reminder should include tasks due tomorrow.

