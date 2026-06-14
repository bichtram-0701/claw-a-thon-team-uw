# Deploy checklist — Funnel Watchtower

Naming is already generic: every workflow uses `RUNTIME_NAME: funnel-watchtower`
and there are no `lending-watchdog` references (legacy is archived). The runtime
name and endpoint URL are **infra-only** — never shown to users or in the agent's
answers. The only "lending" left is the demo data.

Deploy runs on GitHub's servers (the dev sandbox can't reach vngcloud.vn), so this
all happens through the repo's GitHub Actions.

## 0. Get the code into the GitHub repo (one-time)
Copy the contents of `funnel-watchtower/` over your existing repo's working tree
(keep the repo's `.git` so secrets + remote are preserved), then commit.

## 1. Secrets & variables  (repo → Settings → Secrets and variables → Actions)
Secrets:
- `GREENNODE_CLIENT_ID`, `GREENNODE_CLIENT_SECRET`
- `ATLASSIAN_SITE`, `ATLASSIAN_EMAIL`, `ATLASSIAN_TOKEN`
- `LLM_API_KEY`
- `TEAMS_WEBHOOK_URL`, `JIRA_EVENT_TOKEN`  (optional features; degrade gracefully if unset)

Variable (NOT a secret):
- `ALLOW_WRITES = true`  ← **required for the demo**. Deploy defaults it to `false`,
  which disables create / assign / flag / weekly-publish. Without this the write
  features look broken.

Security: **rotate `ATLASSIAN_TOKEN`** — the previous one was shared in a ZIP.
Generate a new Atlassian API token and update the secret.

## 2. Deploy
- Push to `main`, or run Actions → **Deploy to AgentBase** → Run workflow.
- ⚠ Because `funnel-watchtower` doesn't match the old `lending-watchdog` runtime,
  the first deploy **creates a NEW runtime with a NEW endpoint URL**.
- Wait for the run to go green; in the run **Summary**, confirm
  **Serving version == this commit** (proves the new container is actually live).
- Copy the **Endpoint URL** shown in the summary — you need it for step 3.

## 3. Swap in the new endpoint URL (2 places, then redeploy)
Replace the old URL
`https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/...`
with the new one in:
- `chat.html`  (the absolute fallback, ~line 71)
- `SUBMISSION.md`  (live agent link, ~line 50)

Commit & push (chat.html is on the deploy path → redeploys).
Note: the chat UI served *by the agent* calls `/invocations` same-origin, so it
works regardless; this swap is only for opening `chat.html` as a local file and
for the submission link.

## 4. Decommission the old runtime
In the AgentBase console, **stop/delete the old `lending-watchdog` runtime** so it
stops consuming wallet credit alongside the new one.

## 5. Seed + verify
- Run **Verify Atlassian** → confirms credentials + lists the Jira project & Confluence space.
- Run **Seed Atlassian workspace** (reset = true) if the workspace needs the current synthetic data.
- Smoke-test the new endpoint (one of each path):
  - "show me the funnel metrics"   (metrics + target + top recovery priority)
  - "give me daily disburse amount in May"   (analyst / SQL)
  - "flag it"   (impact-ranked investigation, assigned to the owner)
  - "who's working on what"   (oversight by Epic)
  - "weekly summary"   (weekly pack + Confluence publish, if ALLOW_WRITES=true)
- Optional: trigger **LM funnel digest** and **Teams poll/reminders** once.

## Notes
- Offline suite: 78 passed. Live MaaS / Jira / Confluence / Teams are **unverified**
  until the step-5 smoke test — do that before relying on it for the demo.
- If the AgentBase console supports renaming a runtime, you could instead rename the
  existing runtime to `funnel-watchtower` and keep its URL (skips steps 3–4) — but a
  fresh runtime is cleaner.
