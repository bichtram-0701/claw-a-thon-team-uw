# Funnel Watchtower evaluation prompts

Use this file as a small regression set for LLM routing and answer quality.
The offline tests cover many of these as deterministic fallbacks; a live MaaS run
should also check route source, confidence, and final answer quality.

## Routing near-collisions

| Prompt | Expected intent | Notes |
|---|---|---|
| daily volume in May | analyst | Must not route to standup |
| show daily volume | analyst | Analytics request |
| draft my daily standup | standup | Standup keyword must win only with standup context |
| draft my standup | standup | Standard standup request |
| daily approval volume by channel | analyst | SQL-style breakdown |
| weekly volume in May | analyst | Data aggregation, not weekly meeting |
| prepare weekly meeting summary | weekly | Meeting summary |
| publish weekly meeting summary to Confluence | weekly | Weekly + write action |
| show me the funnel metrics | metrics | Standard metric table |
| what is the approval rate? | metrics | Narrow metric question |
| what is critical or off track? | oversight | Manager digest |
| who is working on what? | oversight | Ownership / manager execution view |
| what is on my plate? | briefing | Contributor briefing |
| draft my standup | standup | Contributor update |
| what did we decide about submission? | knowledge | Confluence context |
| flag the approval drop | flag | Jira investigation flow |
| flag it | flag | Contextual flagging |
| create a ticket to improve submission rate | create | Jira create |
| assign KAN-23 to Mai | assign | Jira assign |
| ai dang lam gi, co gi tre khong? | oversight | Vietnamese oversight |

## Answer-quality checks

For metrics answers:

- Must include actual computed rates from `funnel_metrics.py`.
- Must mention impact ranking when target misses exist.
- Must not invent owners or Jira issue keys.

For analyst answers:

- Prefer `source=template` for supported breakdowns.
- Show the SQL.
- Reject or avoid non-read SQL.

For flagging:

- One open investigation per stage + metric + month.
- If an investigation exists, comment/update instead of creating a duplicate.
- Include an investigation contract in the description or comment.

For weekly summary:

- Include executive summary, impact-ranked risks, execution follow-up, Confluence
  context, and proposed agenda.
- If asked to publish and writes are disabled, clearly say it drafted but did not
  publish.
