# Funnel Agent demo video storyboard

Use this for a 2-3 minute recording. The goal is to show the full workflow, not only the chatbot.

## Core story

Funnel Agent is the command center. Jira is the recovery system of record. Confluence is the meeting memory. Teams is the accountability layer.

```text
Detect -> Diagnose -> Assign -> Summarize -> Notify
```

## Frame-by-frame plan

| Frame | Screen | Prompt / action | Annotation overlay | What to show |
|---:|---|---|---|---|
| 1 | Title or chat home | Open Funnel Agent | Every team owns a funnel. The hard part is recovery coordination. | Funnel: Traffic -> Submission -> Approval -> Disbursement |
| 2 | Chat | `/metrics show me the funnel metrics` | Detect target drift and rank business impact. | Approval is top recovery priority; value at risk; MoM table |
| 3 | Chat | `/metrics why is approval the top risk?` | Metric -> target gap -> MoM movement -> value at risk -> owner. | Approval 11.1% vs 15.0%, owner bichtram |
| 4 | Chat | `/metrics break May approval drop down by reason` | Deterministic drilldown, not model guessing. | 216 submitted, 24 approved, 192 dropped; reason table sums to 192 |
| 5 | Chat | `/jira explain stage ownership structure` | Epic -> stage owner -> task assignee. | Approval owner, Submission owner, Disbursement owner |
| 6 | Chat then Jira | `/jira flag the drops and assign owners to investigate` | Metric drift becomes owned recovery work. | Open/update Jira investigations with default assignees |
| 7 | Jira board / issue detail | Open the generated Jira issue | Jira is the recovery system of record. | Assignee, due date, stage labels, evidence, success check |
| 8 | Chat | `/jira what is critical or off track right now?` | Business risk + execution risk in one answer. | Top metric risk + blocked/overdue issues |
| 9 | Chat then Jira issue | `/jira what does blocked mean here and what is it blocking?` | Blocked is a dependency flag, not just a status. | Blocked by / blocks fields for UW issue(s) |
| 10 | Chat | `/confluence weekly meeting summary` | Weekly operating rhythm generated from metrics + Jira + Confluence. | Executive summary, impact-ranked risks, agenda |
| 11 | Chat then Confluence | `/confluence publish weekly meeting summary to Confluence` | Confluence becomes the team memory. | Published page with formatted sections |
| 12 | Chat then Teams | `/teams post off-track blockers` | Teams pushes accountability and reminders. | Teams card with Jira keys, owner, due date, blocker context |
| 13 | End slide | Close | Detect -> Diagnose -> Assign -> Summarize -> Notify. | Funnel Agent closes the recovery loop. |

## Suggested 2-3 minute timing

| Time | Segment |
|---:|---|
| 0:00-0:12 | Problem: dashboards show drift; recovery work is fragmented |
| 0:12-0:35 | `/metrics show me the funnel metrics` |
| 0:35-0:55 | `/metrics why is approval the top risk?` |
| 0:55-1:15 | `/metrics break May approval drop down by reason` |
| 1:15-1:40 | `/jira flag...`, then show Jira issue |
| 1:40-2:00 | `/jira what is critical...`, show blocked issue |
| 2:00-2:25 | Weekly summary + Confluence page |
| 2:25-2:45 | Teams blocker card |
| 2:45-3:00 | Closing line |

## Teams feature framing

The Teams feature is not just another output. It supports the operating rhythm:

1. **New task created** -> Teams card with all fields; empty fields are highlighted.
2. **Task updated** -> Teams card showing field changes from old value to new value.
3. **09:00 digest** -> overdue tasks and stale tasks without updates.
4. **17:00 reminder** -> tasks due tomorrow.

For the live demo, show `/teams post off-track blockers`, then add a short overlay that background workflows also handle new task, task update, 09:00 digest, and 17:00 due-tomorrow reminders.

## Voiceover one-liner

Funnel Agent watches owned funnel metrics, ranks the business risk, turns drift into Jira recovery work, prepares the Confluence weekly review, and pushes blockers to Teams.
