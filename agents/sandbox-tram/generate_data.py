"""Generate a synthetic daily-disbursement dataset (mock data — no real customers).

Sandbox sample for Tram. Produces ~70 days of loan disbursement records ending at
a fixed "today" so the metrics are deterministic and reproducible.

Run:  python generate_data.py
Out:  data/disbursements.csv
"""
import os
import csv
import random
from datetime import date, timedelta

# Fixed reference "today" so results are stable run-to-run (no real-clock dependency).
TODAY = date(2026, 6, 11)
DAYS = 70  # history depth

PRODUCTS = ["CashLoan", "BNPL", "CreditLine", "AutoLoan"]
REGIONS = ["North", "Central", "South"]
# weighted: most transactions succeed
STATUSES = (["success"] * 85) + (["failed"] * 10) + (["pending"] * 5)

random.seed(42)  # reproducible

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT_PATH = os.path.join(OUT_DIR, "disbursements.csv")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    cust_seq = 1000

    start = TODAY - timedelta(days=DAYS - 1)
    for d in range(DAYS):
        day = start + timedelta(days=d)
        # Weekends are slower; add a gentle upward trend over time.
        is_weekend = day.weekday() >= 5
        base_loans = 18 if is_weekend else 40
        trend = 1.0 + d * 0.004  # ~0.4%/day growth
        n_loans = max(1, int(base_loans * trend * random.uniform(0.8, 1.2)))

        for _ in range(n_loans):
            cust_seq += 1
            amount = int(random.uniform(3_000_000, 80_000_000))  # VND
            rows.append({
                "disbursement_date": day.isoformat(),
                "customer_id": f"C{cust_seq:06d}",
                "disbursement_amount_vnd": amount,
                "status": random.choice(STATUSES),
                "product": random.choice(PRODUCTS),
                "region": random.choice(REGIONS),
            })

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows):,} rows across {DAYS} days -> {OUT_PATH}")
    print(f'"Today" in this dataset = {TODAY.isoformat()}')


if __name__ == "__main__":
    main()
