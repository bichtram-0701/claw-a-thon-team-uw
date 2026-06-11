"""Tiny rule-based 'agent' over the disbursement data — sandbox sample.

Not the real LLM agent — just enough to see data -> question -> answer working.
Later this maps onto: user question -> tool (metrics) -> LLM phrases the answer.

Run:
  python ask.py                              # demo: runs all sample questions
  python ask.py "MPU this week vs last week"
"""
import os
import sys

import metrics

DATA = os.path.join(os.path.dirname(__file__), "data", "disbursements.csv")


def vnd(x):
    return f"{x:,.0f} VND"


def _arrow(pct):
    return "up" if (pct or 0) >= 0 else "down"


def answer(df, q: str) -> str:
    ql = q.lower()
    w = metrics.week_over_week(df)
    tw, lw = w["this_week"], w["last_week"]

    if "mpu" in ql or "user" in ql:
        p = w["mpu_change_pct"]
        return (
            f"MPU (users with transaction) this week ({tw['from']}..{tw['to']}) = "
            f"{tw['mpu']:,} vs last week ({lw['from']}..{lw['to']}) {lw['mpu']:,} "
            f"-> {_arrow(p)} {abs(p)}%."
        )

    # default: total disbursement (success only) this week vs last week
    p = w["total_disbursement_change_pct"]
    return (
        f"Total disbursement (success) this week ({tw['from']}..{tw['to']}) = "
        f"{vnd(tw['total_disbursement_vnd'])} vs last week ({lw['from']}..{lw['to']}) "
        f"{vnd(lw['total_disbursement_vnd'])} -> {_arrow(p)} {abs(p)}%."
    )


def main():
    if not os.path.exists(DATA):
        sys.exit("No data yet. Run:  python generate_data.py")
    df = metrics.load(DATA)

    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(f"Q: {q}\nA: {answer(df, q)}")
        return

    demo = [
        "total disbursement this week vs last week",
        "change in MPU this week vs last week",
    ]
    for q in demo:
        print(f"Q: {q}\nA: {answer(df, q)}\n")


if __name__ == "__main__":
    main()
