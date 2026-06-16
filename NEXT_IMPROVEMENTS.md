# Next improvements beyond demo-v28

Funnel Agent is strong enough for the Claw-a-thon demo, but it can still improve. The highest-value next steps are:

1. **Closed-loop outcome tracking** — when a Jira recovery task is completed, compare before/after funnel metrics and classify the action as worked, partially worked, no measurable impact, or inconclusive.
2. **Configurable funnel schema** — move Traffic → Submission → Approval → Disbursement into a YAML/JSON config so other teams can define their own funnel stages, targets, owners, and value-at-risk formulas.
3. **Real data connector** — replace the synthetic CSV with a warehouse/BI/event-log connector while keeping the same deterministic aggregation and audit SQL pattern.
4. **Better dependency graph** — use Jira issue links (`blocks`, `is blocked by`) instead of only labels/descriptions for blocker reasoning.
5. **Production governance** — add user auth, role-based write permissions, confirmation modals for external writes, and a persistent audit log.
6. **Evaluation dashboard** — track intent route, slots, tool calls, response validation, latency, and live integration failures across the demo prompt matrix.

Do not implement all of this before the demo. For the competition, focus on a clean recording of the end-to-end workflow: Detect → Diagnose → Assign → Summarize → Notify.
