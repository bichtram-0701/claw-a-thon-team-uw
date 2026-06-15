# Data design

The demo data now uses one row-level source of truth:

```text
data/funnel_synthetic.csv
```

Monthly metrics are aggregated from this CSV, so daily, monthly, segment, and drop-reason views reconcile.

## Core modeling choice

One row represents one distinct synthetic user/entity that entered the funnel.

For demo simplicity:

```text
one row = one user/entity = one application/request
```

A user/entity may enter the funnel as traffic but never submit to the partner/system.

## Funnel stages

```text
Traffic -> Submission -> Approval -> Disbursement
```

`final_stage` records the furthest stage reached:

| `final_stage` | Meaning | `stage_rank` |
|---|---|---:|
| `traffic` | Entered funnel but did not submit | 1 |
| `submitted` | Submitted but did not get approved | 2 |
| `approved` | Approved but did not disburse | 3 |
| `completed` (internal) / `disbursed` | Reaches disbursement | 4 |

Counting rules:

```text
Traffic    = COUNT(*)
Submission = COUNT(stage_rank >= 2)
Approval   = COUNT(stage_rank >= 3)
Disbursement = COUNT(stage_rank = 4)
```

Conversion rates:

```text
submission_rate = Submission / Traffic
approval_rate   = Approval / Submission
completion_rate (internal key) = Disbursement / Approval
e2e_rate        = Disbursement / Traffic
```

## CSV schema

| Column | Meaning |
|---|---|
| `entity_id` | Synthetic distinct user/entity ID |
| `product_type` | Synthetic segment: `standard_application`, `premium_application`, `express_application`, `partner_application` |
| `channel` | Source channel: `web`, `mobile_app`, `agent_referral` |
| `entered_date` | Date the user/entity entered the funnel |
| `iso_week` | ISO week derived from `entered_date` |
| `potential_value_vnd` | Synthetic potential/disbursed value in VND |
| `final_stage` | Furthest stage reached: `traffic`, `submitted`, `approved`, `completed`/`disbursed` |
| `drop_transition` | Failed transition for non-disbursed rows |
| `drop_reason` | Reason the user/entity did not reach the next stage; blank when disbursed |

## Drop logic

`drop_reason` exists for every non-disbursed row.

| `final_stage` | `drop_transition` | Example `drop_reason` values |
|---|---|---|
| `traffic` | `traffic_to_submission` | `did_not_submit`, `abandoned_before_submit`, `no_partner_selected`, `not_ready`, `duplicate_entry` |
| `submitted` | `submission_to_approval` | `policy_check`, `eligibility_check`, `docs_invalid`, `docs_abandoned` |
| `approved` | `approval_to_disbursement` | `customer_withdrew`, `offer_expired`, `ops_timeout`, `partner_unavailable` |
| `completed` (internal) / `disbursed` | blank | blank |

This means `/metrics break May approval drop down by reason` can answer the Submission -> Approval loss directly:

```text
May submitted: 216
May approved: 24
Submitted but not approved: 192
```

Expected May Submission -> Approval drop reasons:

| Drop reason | Count |
|---|---:|
| `policy_check` | 90 |
| `docs_invalid` | 46 |
| `eligibility_check` | 38 |
| `docs_abandoned` | 18 |
| **Total** | **192** |

## Current monthly totals

| Month | Traffic | Submission | Approval | Disbursement |
|---|---:|---:|---:|---:|
| 2025-12 | 750 | 240 | 34 | 33 |
| 2026-01 | 780 | 273 | 41 | 39 |
| 2026-02 | 650 | 156 | 28 | 27 |
| 2026-03 | 820 | 246 | 32 | 31 |
| 2026-04 | 850 | 238 | 36 | 35 |
| 2026-05 | 800 | 216 | 24 | 23 |

The full CSV has 4,650 rows across six demo months.

## SQL view

`sql_analyst.py` exposes the CSV through a DuckDB view named `funnel`.

The view adds:

```text
entered_dt
stage_rank
funnel_stage
```

It also keeps a few compatibility aliases for older prompts/docs:

```text
app_id = entity_id
applied_date = entered_date
applied_dt = entered_dt
requested_vnd = potential_value_vnd
```

Templates should use the generic names: `entity_id`, `entered_dt`, `potential_value_vnd`, `final_stage`, `drop_transition`, and `drop_reason`.

## Jira blocker semantics

In the demo Jira data, `blocked` is an execution flag, usually a Jira label. It is not necessarily the Jira workflow status. An issue can therefore have:

```text
workflow status = To Do
labels          = blocked
```

That means the task has not started or cannot progress because of a dependency. When blocker context is available, the issue also carries:

```text
blocked_by = the dependency that prevents progress
blocks     = the downstream work or metric confidence affected by the blocker
```

Example seeded blockers:

| Issue summary | Blocked by | Blocks |
|---|---|---|
| Disbursement timestamp mismatch | verification status-map alignment from the partner feed | reliable Disbursement timestamp reconciliation and disbursement reporting |
| Missing records in the E2E funnel log | upstream event-feed/backfill from the data platform | complete E2E funnel-log coverage and weekly metric confidence |
