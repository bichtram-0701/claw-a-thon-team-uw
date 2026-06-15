from __future__ import annotations

import csv
import json
import random
from calendar import monthrange
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
METRICS = DATA_DIR / "funnel_metrics.json"
OUT = DATA_DIR / "funnel_synthetic.csv"

PRODUCTS = ["standard_application", "premium_application", "express_application", "partner_application"]
CHANNELS = ["web", "mobile_app", "agent_referral"]

# Slightly different weights by stage so diagnostics have visible but realistic signals.
PRODUCT_WEIGHTS_BASE = {
    "traffic": [0.44, 0.24, 0.22, 0.10],
    "submitted": [0.25, 0.14, 0.21, 0.40],
    "approved": [0.39, 0.36, 0.16, 0.09],
    "completed": [0.40, 0.35, 0.16, 0.09],
}
CHANNEL_WEIGHTS_BASE = {
    "traffic": [0.44, 0.42, 0.14],
    "submitted": [0.25, 0.20, 0.55],
    "approved": [0.34, 0.48, 0.18],
    "completed": [0.34, 0.48, 0.18],
}

VALUE_RANGES = {
    "standard_application": (12_000_000, 60_000_000),
    "premium_application": (50_000_000, 180_000_000),
    "express_application": (3_000_000, 16_000_000),
    "partner_application": (5_000_000, 35_000_000),
}

TRAFFIC_DROP_REASONS = ["did_not_submit", "abandoned_before_submit", "no_partner_selected", "not_ready", "duplicate_entry"]
TRAFFIC_DROP_WEIGHTS = [0.42, 0.24, 0.16, 0.13, 0.05]

SUBMISSION_DROP_REASONS = ["policy_check", "eligibility_check", "docs_invalid", "docs_abandoned"]
SUBMISSION_DROP_WEIGHTS = {
    # May is intentionally worse and more policy/eligibility heavy for the demo.
    "2026-05": [0.47, 0.20, 0.22, 0.11],
    "default": [0.36, 0.18, 0.24, 0.22],
}

COMPLETION_DROP_REASONS = ["customer_withdrew", "offer_expired", "ops_timeout", "partner_unavailable"]
COMPLETION_DROP_WEIGHTS = [0.45, 0.20, 0.25, 0.10]

STAGE_TRANSITION = {
    "traffic": "traffic_to_submission",
    "submitted": "submission_to_approval",
    "approved": "approval_to_completion",
    "completed": "",
}


def _weighted_choice(rng: random.Random, values: list[str], weights: list[float]) -> str:
    return rng.choices(values, weights=weights, k=1)[0]


def _month_dates(month: str) -> list[date]:
    y, m = map(int, month.split("-"))
    return [date(y, m, d) for d in range(1, monthrange(y, m)[1] + 1)]


def _daily_weights(dates: list[date]) -> list[float]:
    # Keep every day populated, with weekdays slightly heavier than weekends.
    return [1.15 if d.weekday() < 5 else 0.75 for d in dates]


def _potential_value_vnd(rng: random.Random, product: str) -> int:
    low, high = VALUE_RANGES[product]
    # Rounded to 1M VND for readable mock data.
    return rng.randrange(low // 1_000_000, high // 1_000_000 + 1) * 1_000_000


def _stage_rows(metrics: dict) -> list[str]:
    traffic = int(metrics["traffic"])
    submitted = int(metrics["submission"])
    approved = int(metrics["approval"])
    completed = int(metrics["completion"])
    return (
        ["traffic"] * (traffic - submitted)
        + ["submitted"] * (submitted - approved)
        + ["approved"] * (approved - completed)
        + ["completed"] * completed
    )


def _drop_reason(rng: random.Random, stage: str, month: str) -> str:
    if stage == "traffic":
        return _weighted_choice(rng, TRAFFIC_DROP_REASONS, TRAFFIC_DROP_WEIGHTS)
    if stage == "submitted":
        weights = SUBMISSION_DROP_WEIGHTS.get(month, SUBMISSION_DROP_WEIGHTS["default"])
        return _weighted_choice(rng, SUBMISSION_DROP_REASONS, weights)
    if stage == "approved":
        return _weighted_choice(rng, COMPLETION_DROP_REASONS, COMPLETION_DROP_WEIGHTS)
    return ""


def generate() -> None:
    rng = random.Random(20260614)
    meta = json.loads(METRICS.read_text(encoding="utf-8"))
    entity_no = 1
    rows: list[dict[str, object]] = []

    for m in meta["months"]:
        month = m["month"]
        dates = _month_dates(month)
        stage_rows = _stage_rows(m)
        rng.shuffle(stage_rows)
        day_weights = _daily_weights(dates)
        target_completed_amount = int(m["completion_amount_vnd"])
        completed_indices: list[int] = []
        month_rows: list[dict[str, object]] = []

        for stage in stage_rows:
            dt = _weighted_choice(rng, dates, day_weights)
            product_weights = PRODUCT_WEIGHTS_BASE[stage]
            channel_weights = CHANNEL_WEIGHTS_BASE[stage]

            # Make the May approval failure signal visible in diagnostics.
            if month == "2026-05" and stage == "submitted":
                product_weights = [0.22, 0.12, 0.18, 0.48]
                channel_weights = [0.20, 0.18, 0.62]

            product = _weighted_choice(rng, PRODUCTS, product_weights)
            channel = _weighted_choice(rng, CHANNELS, channel_weights)
            row = {
                "entity_id": f"E{entity_no:05d}",
                "product_type": product,
                "channel": channel,
                "entered_date": dt.isoformat(),
                "iso_week": int(dt.isocalendar().week),
                "potential_value_vnd": _potential_value_vnd(rng, product),
                "final_stage": stage,
                "drop_transition": STAGE_TRANSITION[stage],
                "drop_reason": _drop_reason(rng, stage, month),
            }
            if stage == "completed":
                completed_indices.append(len(month_rows))
            month_rows.append(row)
            entity_no += 1

        # Adjust completed rows so their potential_value_vnd sum exactly matches the
        # monthly disbursement volume used by value-at-risk math.
        if completed_indices:
            base = target_completed_amount // len(completed_indices)
            remainder = target_completed_amount - base * len(completed_indices)
            rng.shuffle(completed_indices)
            for offset, idx in enumerate(completed_indices):
                month_rows[idx]["potential_value_vnd"] = base + (1 if offset < remainder else 0)

        rows.extend(month_rows)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "entity_id",
                "product_type",
                "channel",
                "entered_date",
                "iso_week",
                "potential_value_vnd",
                "final_stage",
                "drop_transition",
                "drop_reason",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    generate()
