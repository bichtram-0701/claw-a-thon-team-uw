# Funnel Agent 2-minute demo clip script

Use this as the recording script. The video should show real screens, not generated UI. The main proof is the flow across **Funnel Agent -> Jira -> Confluence -> Teams**.

## Story thesis

**Funnel Agent turns funnel drift into owned recovery work.**

A dashboard can show that a metric moved. Funnel Agent connects that movement to business impact, Jira ownership, Confluence meeting memory, and Teams follow-up.

## 2-minute frame-by-frame script

### 0:00-0:10 — Introduction

**Screen:** Funnel Agent home screen.

**Narration:**
> This is Funnel Agent. It helps business teams turn funnel drift into owned recovery work across Jira, Confluence, and Teams. The demo funnel is Traffic to Submission to Approval to Disbursement.

**Overlay:**
> Detect -> Diagnose -> Assign -> Summarize -> Notify

---

### 0:10-0:25 — Interaction 1: detect risk

**Prompt typed:**
```text
show me the funnel metrics
```

**Bot line to highlight/read:**
> Top recovery priority: Approval — estimated value at risk 108.1M VND.

**Narration:**
> The agent queries the funnel data, computes conversion rates and month-over-month movement, then ranks the recovery priority. Approval is the top risk because it has the largest value at risk.

**Zoom target:** Approval row in impact ranking.

---

### 0:25-0:38 — Interaction 2: explain top risk

**Prompt typed:**
```text
why is approval the top risk?
```

**Bot line to highlight/read:**
> Approval is the top risk because it combines the largest business impact with a material funnel signal.

**Narration:**
> The answer connects target gap, month-over-month movement, value at risk, owner, and execution context. This is business reasoning on top of deterministic numbers.

**Zoom target:** Signal, value at risk, owner, execution context bullets.

---

### 0:38-0:53 — Interaction 3: reconcile the drop

**Prompt typed:**
```text
break May approval drop down by reason
```

**Bot line to highlight/read:**
> Submission to Approval reconciliation: 216 submitted, 24 approved, so 192 dropped before Approval.

**Narration:**
> The diagnostic table reconciles exactly to the funnel. The default view is manager-readable, and the Audit SQL is available when someone wants to inspect the query.

**Zoom target:** Drop reason table and Audit SQL expander.

---

### 0:53-1:16 — Interaction 4: create or update Jira work

**Prompt typed:**
```text
/jira flag the drops and assign owners to investigate
```

**Bot line to highlight/read:**
> No assignee was mentioned; defaulting to the Approval stage owner from the Epic -> task structure.

**Narration:**
> This is where it becomes an agent, not just a chatbot. Funnel Agent updates Jira recovery work and defaults the assignee from the stage ownership model.

**Screen cut:** Open the linked Jira issue.

**Jira overlay:**
> Metric evidence + owner + due date + success check

---

### 1:16-1:32 — Interaction 5: execution context

**Prompt typed:**
```text
/jira what is critical or off track right now?
```

**Bot line to highlight/read:**
> Critical / off-track snapshot: impact-ranked funnel risks, needs attention now, and due soon.

**Narration:**
> The manager can now see both business risk and execution risk: blocked work, overdue work, owners, and due dates.

**Zoom target:** Needs attention now table.

---

### 1:32-1:47 — Interaction 6: weekly readout

**Prompt typed:**
```text
weekly meeting summary
```

**Bot line to highlight/read:**
> Funnel Agent Weekly Readout: executive summary, impact ranking, needs attention now, recently completed, Confluence context, and recommended agenda.

**Narration:**
> The weekly summary turns live metrics and Jira execution state into a meeting-ready readout.

**Zoom target:** Executive summary and recommended agenda.

---

### 1:47-1:58 — Interaction 7: publish to Confluence

**Prompt typed:**
```text
/confluence publish weekly meeting summary to Confluence
```

**Bot line to highlight/read:**
> Published or updated the weekly summary in Confluence.

**Narration:**
> The readout is saved to Confluence, so decisions and follow-ups become team memory.

**Screen cut:** Confluence page.

---

### 1:58-2:10 — Interaction 8: notify Teams and close

**Prompt typed:**
```text
/teams post off-track blockers
```

**Bot line to highlight/read:**
> Posted off-track items to Teams.

**Narration:**
> Finally, blockers are pushed to Teams. Funnel Agent closes the loop: Detect, Diagnose, Assign, Summarize, and Notify.

**Screen cut:** Teams card.

**Final overlay:**
> Funnel Agent: turns funnel drift into owned recovery work.

## Optional extra if you have 10 more seconds

Use this if you want to explain blocker semantics:

```text
/jira what does blocked mean here and what is it blocking?
```

**Bot line to highlight/read:**
> Blocked is a Jira label or dependency flag, not necessarily the workflow status.
