"""Portfolio metric computations — Lending Portfolio Watchdog, Team UW.

Schema-tolerant: accepts both the synthetic watchdog tape (outstanding_vnd,
product_type, province) and generic loan tapes (outstanding_balance_vnd,
product, region) via column aliases.
"""
import io
import pandas as pd

# canonical name -> accepted aliases (first found wins)
COLUMN_ALIASES = {
    "outstanding_balance_vnd": ["outstanding_balance_vnd", "outstanding_vnd"],
    "product": ["product", "product_type"],
    "region": ["region", "province"],
}

DPD_BUCKETS = [
    ("Current", 0, 0),
    ("DPD 1-30", 1, 30),
    ("DPD 31-60", 31, 60),
    ("DPD 61-90", 61, 90),
    ("NPL (90+)", 91, 10**6),
]

REQUIRED = {"loan_id", "product", "outstanding_balance_vnd", "days_past_due"}


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    for canon, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in df.columns:
                if a != canon:
                    df = df.rename(columns={a: canon})
                break
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    return df


def load_csv(text: str) -> pd.DataFrame:
    return normalize(pd.read_csv(io.StringIO(text)))


def from_rows(rows: list[dict]) -> pd.DataFrame:
    return normalize(pd.DataFrame(rows))


def analyze(df: pd.DataFrame) -> dict:
    """Compute portfolio risk metrics from a loan tape."""
    bal = df["outstanding_balance_vnd"].astype(float)
    total = float(bal.sum())
    n = len(df)

    buckets = []
    for name, lo, hi in DPD_BUCKETS:
        mask = (df["days_past_due"] >= lo) & (df["days_past_due"] <= hi)
        buckets.append({
            "bucket": name,
            "loans": int(mask.sum()),
            "balance_vnd": float(bal[mask].sum()),
            "balance_pct": round(100 * float(bal[mask].sum()) / total, 2) if total else 0.0,
        })

    npl_balance = float(bal[df["days_past_due"] > 90].sum())
    delinq_balance = float(bal[df["days_past_due"] > 0].sum())

    def concentration(col):
        if col not in df.columns:
            return []
        g = df.groupby(col)["outstanding_balance_vnd"].sum().sort_values(ascending=False)
        return [{"name": str(k), "balance_pct": round(100 * float(v) / total, 2)} for k, v in g.items()]

    out = {
        "loans": n,
        "total_outstanding_vnd": total,
        "npl_ratio_pct": round(100 * npl_balance / total, 2) if total else 0.0,
        "delinquency_ratio_pct": round(100 * delinq_balance / total, 2) if total else 0.0,
        "dpd_buckets": buckets,
        "by_product": concentration("product"),
        "by_region": concentration("region"),
        "by_segment": concentration("segment"),
    }
    if "as_of_date" in df.columns:
        out["as_of_date"] = str(df["as_of_date"].iloc[0])
    if "interest_rate_pct" in df.columns and total:
        out["wavg_interest_rate_pct"] = round(float((df["interest_rate_pct"].astype(float) * bal).sum() / total), 2)
    return out


def compare(current: dict, previous: dict) -> dict:
    """Period-over-period deltas (percentage points / percent)."""
    return {
        "npl_ratio_pp": round(current["npl_ratio_pct"] - previous["npl_ratio_pct"], 2),
        "delinquency_ratio_pp": round(current["delinquency_ratio_pct"] - previous["delinquency_ratio_pct"], 2),
        "outstanding_growth_pct": round(
            100 * (current["total_outstanding_vnd"] / previous["total_outstanding_vnd"] - 1), 2
        ) if previous["total_outstanding_vnd"] else None,
        "loan_count_change": current["loans"] - previous["loans"],
    }
