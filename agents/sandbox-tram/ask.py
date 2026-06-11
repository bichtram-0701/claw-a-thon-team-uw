"""Sandbox disbursement agent: question -> compute facts -> phrase answer.

Pattern (important): numbers are computed deterministically in `metrics.py` so
they are always correct. Qwen (via MaaS) only *phrases* those facts into a
natural Vietnamese sentence. If no LLM key is set, we fall back to a fixed
template so the demo never breaks.

Run:
  python ask.py                              # demo questions
  python ask.py "MPU tuần này so với tuần trước"
"""
import os
import sys

import metrics
from llm_client import LLMClient

DATA = os.path.join(os.path.dirname(__file__), "data", "disbursements.csv")

_llm = LLMClient()

SYSTEM = (
    "Bạn là trợ lý phân tích rủi ro tín dụng, trả lời ngắn gọn bằng tiếng Việt. "
    "Chỉ dùng đúng các con số trong dữ liệu được cung cấp — TUYỆT ĐỐI không bịa số. "
    "Trả lời tự nhiên, súc tích (2-3 câu), nêu rõ xu hướng tăng/giảm và đưa 1 nhận xét ngắn."
)


def vnd(x):
    return f"{x:,.0f} VND"


def _facts(df, q: str) -> dict:
    """Pick the metric the question is about and return structured facts."""
    ql = q.lower()
    w = metrics.week_over_week(df)
    tw, lw = w["this_week"], w["last_week"]
    if "mpu" in ql or "user" in ql:
        return {
            "metric": "MPU (số user có giao dịch)",
            "this_week": f"{tw['from']}..{tw['to']}: {tw['mpu']:,} users",
            "last_week": f"{lw['from']}..{lw['to']}: {lw['mpu']:,} users",
            "change_pct": w["mpu_change_pct"],
        }
    return {
        "metric": "Tổng giải ngân (status=success)",
        "this_week": f"{tw['from']}..{tw['to']}: {vnd(tw['total_disbursement_vnd'])}",
        "last_week": f"{lw['from']}..{lw['to']}: {vnd(lw['total_disbursement_vnd'])}",
        "change_pct": w["total_disbursement_change_pct"],
    }


def _template(f: dict) -> str:
    arrow = "tăng" if (f["change_pct"] or 0) >= 0 else "giảm"
    return (f"{f['metric']} — tuần này {f['this_week']}; tuần trước {f['last_week']}. "
            f"=> {arrow} {abs(f['change_pct'])}% so với tuần trước.")


def answer(df, q: str) -> str:
    f = _facts(df, q)
    if not _llm.available:
        return _template(f)
    user = (
        f"Câu hỏi: {q}\n"
        f"Chỉ số: {f['metric']}\n"
        f"Tuần này — {f['this_week']}\n"
        f"Tuần trước — {f['last_week']}\n"
        f"Thay đổi: {f['change_pct']}%\n"
        f"Hãy viết câu trả lời tự nhiên cho người dùng."
    )
    try:
        return _llm.chat(SYSTEM, user)
    except Exception:
        return _template(f)  # never break the demo


def main():
    if not os.path.exists(DATA):
        sys.exit("No data yet. Run:  python generate_data.py")
    df = metrics.load(DATA)
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(f"Q: {q}\nA: {answer(df, q)}")
        return
    for q in ["Tổng giải ngân tuần này so với tuần trước",
              "MPU tuần này so với tuần trước"]:
        print(f"Q: {q}\nA: {answer(df, q)}\n")


if __name__ == "__main__":
    main()
