"""Disbursement metrics for the sandbox sample — week-over-week.

Definitions (per the team):
  - MPU               = number of distinct users who have a transaction in the period
  - total_disbursement = sum of amount where status == "success"

Comparison: THIS WEEK vs LAST WEEK, as rolling 7-day windows ending at the
latest date in the data ("today").

Pure pandas.
"""
from datetime import timedelta

import pandas as pd

SUCCESS = "success"


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["disbursement_date"])
    df["d"] = df["disbursement_date"].dt.date
    return df


def _window(df: pd.DataFrame, lo, hi) -> pd.DataFrame:
    """Rows with date in [lo, hi] inclusive."""
    return df[(df["d"] >= lo) & (df["d"] <= hi)]


def _period_metrics(rows: pd.DataFrame) -> dict:
    success = rows[rows["status"] == SUCCESS]
    return {
        "mpu": int(rows["customer_id"].nunique()),                       # users w/ transaction
        "total_disbursement_vnd": float(success["disbursement_amount_vnd"].sum()),  # success only
        "transactions": int(len(rows)),
        "successful_transactions": int(len(success)),
    }


def _pct_change(curr: float, prev: float):
    if prev in (0, None) or pd.isna(prev):
        return None
    return round(100 * (curr / prev - 1), 2)


def week_over_week(df: pd.DataFrame) -> dict:
    """This week (last 7 days) vs last week (the 7 days before that)."""
    today = df["d"].max()
    this_start = today - timedelta(days=6)          # 7-day window inclusive
    last_end = this_start - timedelta(days=1)
    last_start = last_end - timedelta(days=6)

    this_m = _period_metrics(_window(df, this_start, today))
    last_m = _period_metrics(_window(df, last_start, last_end))

    return {
        "this_week": {"from": str(this_start), "to": str(today), **this_m},
        "last_week": {"from": str(last_start), "to": str(last_end), **last_m},
        "mpu_change_pct": _pct_change(this_m["mpu"], last_m["mpu"]),
        "total_disbursement_change_pct": _pct_change(
            this_m["total_disbursement_vnd"], last_m["total_disbursement_vnd"]
        ),
    }
