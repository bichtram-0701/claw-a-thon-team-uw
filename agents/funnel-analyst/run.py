#!/usr/bin/env python3
"""
CLI entrypoint for the Conversion Funnel Analyst agent.

Examples:
    python run.py                                  # uses bundled synthetic data
    python run.py --data data/sample_funnel.csv    # explicit file
    python run.py --data my.csv --out report.md    # save report

Remember: input data must be SYNTHETIC, public, or anonymized (no real customer
data / PII / confidential internal data) per the Claw-a-thon Tool Access Guideline.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent import run  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Conversion Funnel Analyst agent")
    ap.add_argument("--data", default="data/sample_funnel.csv",
                    help="Path to a synthetic/public funnel CSV.")
    ap.add_argument("--config", default=None, help="Path to funnel config.json.")
    ap.add_argument("--out", default=None, help="Write the report to this file.")
    a = ap.parse_args()

    result = run(a.data, config_path=a.config)

    v = result["verification"]
    print(f"[verify] passed={v['passed']}"
          + ("" if v["passed"] else f"  problems={v['problems']}"))
    print(f"[llm] used={result['used_llm']} model={result['model']}\n")
    print(result["report_markdown"])

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fp:
            fp.write(result["report_markdown"])
        print(f"\n[saved] {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
