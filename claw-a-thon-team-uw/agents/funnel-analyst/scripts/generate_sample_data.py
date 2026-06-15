#!/usr/bin/env python3
"""
Generate 100% SYNTHETIC funnel data for the Conversion Funnel Analyst agent.

Compliance (GreenNode Claw-a-thon Tool Access Guideline): this data is fully
synthetic — no real users, no PII, no internal/confidential data. Safe to use,
commit, and demo. Seeded for reproducibility.

Demo funnel: a generic SaaS onboarding funnel.
    Visited -> Signed Up -> Activated -> Subscribed -> Renewed
"""
import csv
import os
import random
import datetime as dt

random.seed(2026)

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "sample_funnel.csv")

CHANNELS = [("Organic", 0.24), ("Paid Search", 0.21), ("Social", 0.17),
            ("Referral", 0.16), ("Email", 0.12), ("Partner", 0.10)]
PLANS    = [("Starter", 0.50), ("Pro", 0.35), ("Enterprise", 0.15)]
REGIONS  = [("APAC", 0.34), ("EMEA", 0.30), ("AMER", 0.36)]
DEVICES  = [("Desktop", 0.55), ("Mobile", 0.38), ("Tablet", 0.07)]

# base stage-to-stage conversion, modulated by channel/plan
BASE = {
    "signed_up":  0.42,   # Visited -> Signed Up
    "activated":  0.63,   # Signed Up -> Activated
    "subscribed": 0.48,   # Activated -> Subscribed
    "renewed":    0.71,   # Subscribed -> Renewed
}
CHANNEL_SIGNUP_MULT = {"Organic": 1.06, "Paid Search": 0.92, "Social": 0.85,
                       "Referral": 1.18, "Email": 1.10, "Partner": 0.95}
PLAN_SUB_MULT = {"Starter": 0.92, "Pro": 1.08, "Enterprise": 1.20}


def pick(dist):
    r = random.random(); c = 0
    for k, p in dist:
        c += p
        if r <= c:
            return k
    return dist[-1][0]


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    start = dt.datetime(2026, 1, 1)
    rows = []
    N = 15000
    for i in range(N):
        uid = f"U{200000 + i}"          # synthetic id, not a real person
        ch = pick(CHANNELS); plan = pick(PLANS)
        reg = pick(REGIONS); dev = pick(DEVICES)
        cur = start + dt.timedelta(minutes=random.randint(0, 150 * 24 * 60))
        ts = {"visited_at": cur}

        def adv(p, lo, hi):
            nonlocal cur
            if random.random() < min(p, 0.985):
                cur = cur + dt.timedelta(hours=random.uniform(lo, hi))
                return cur
            return None

        s1 = adv(BASE["signed_up"] * CHANNEL_SIGNUP_MULT[ch], 0.05, 24)
        ts["signed_up_at"] = s1
        if s1:
            s2 = adv(BASE["activated"], 0.5, 72); ts["activated_at"] = s2
            if s2:
                s3 = adv(BASE["subscribed"] * PLAN_SUB_MULT[plan], 1, 96)
                ts["subscribed_at"] = s3
                ts["renewed_at"] = adv(BASE["renewed"], 24, 24 * 35) if s3 else None
            else:
                ts["subscribed_at"] = ts["renewed_at"] = None
        else:
            ts["activated_at"] = ts["subscribed_at"] = ts["renewed_at"] = None

        def f(x):
            return x.strftime("%Y-%m-%d %H:%M") if x else ""

        rows.append([uid, ch, plan, reg, dev,
                     f(ts["visited_at"]), f(ts["signed_up_at"]),
                     f(ts["activated_at"]), f(ts["subscribed_at"]),
                     f(ts["renewed_at"])])

    hdr = ["user_id", "channel", "plan", "region", "device",
           "visited_at", "signed_up_at", "activated_at",
           "subscribed_at", "renewed_at"]
    with open(OUT, "w", newline="") as fp:
        w = csv.writer(fp); w.writerow(hdr); w.writerows(rows)
    print(f"Wrote {len(rows):,} synthetic rows to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
