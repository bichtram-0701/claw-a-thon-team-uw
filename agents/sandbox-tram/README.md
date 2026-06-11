# Sandbox — Tram (sample agent, learning only)

A throwaway sample to learn the data → question → answer flow before building the
real action module (Scope B: Jira/Confluence). **Mock data only — no real customers.**

## What it does
Answers disbursement questions over a synthetic daily dataset, **this week vs last week**:
- **MPU** = number of distinct users who have a transaction
- **total_disbursement** = sum of amount where `status == success`

Comparison windows are rolling 7 days ending at the latest date in the data.

## Files
| File | Role |
|------|------|
| `generate_data.py` | Builds `data/disbursements.csv` (70 days, ends 2026-06-11) |
| `metrics.py` | The "tools" — time-series calculations (pandas) |
| `ask.py` | Tiny rule-based agent: question in, answer out |
| `server.py` | HTTP wrapper for AgentBase: `GET /health`, `GET /ask`, `POST /invocations` |
| `Dockerfile` | Container image (port 8080) for deploying to AgentBase |

## Deploy to AgentBase
Contract: container listens on port 8080, `GET /health` returns 200 (satisfied by `server.py`).
1. Start Docker Desktop.
2. `docker build --platform linux/amd64 -t sandbox-tram:latest .`
3. Use the `agentbase-deploy` skill (needs IAM credentials from the Training-day email).

## Run
```powershell
# python path on this machine:
$py = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
& $py -m pip install pandas      # once
& $py generate_data.py           # make the data
& $py ask.py                     # run all sample questions
& $py ask.py "MPU this week vs last week"   # ask one
```

## Note
"Today" = the latest date in the CSV (deterministic, not the real clock).
