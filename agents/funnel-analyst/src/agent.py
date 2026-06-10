"""
Conversion Funnel Analyst — agent orchestrator.

This is the single entrypoint the AgentBase wrapper binds to. It runs the four
steps of the Data Analysis track: RETRIEVE -> ANALYZE -> SYNTHESIZE -> REPORT.
"""
from __future__ import annotations

import json
import os

from .funnel import FunnelAnalyzer, load_rows
from .llm_client import LLMClient
from .synthesize import synthesize_report

_DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "..", "config.json")


def load_config(path: str | None = None) -> dict:
    with open(path or _DEFAULT_CONFIG) as fp:
        return json.load(fp)


def run(data_path: str,
        config_path: str | None = None,
        client: LLMClient | None = None) -> dict:
    """Main agent call.

    Args:
        data_path: path to a CSV of SYNTHETIC / public / anonymized funnel data.
        config_path: optional path to a funnel config (stages + segments).
        client: optional pre-built LLMClient (else built from env).

    Returns:
        dict with keys: report_markdown, analysis, verification, used_llm, model.
    """
    cfg = load_config(config_path)

    # 1. RETRIEVE
    rows = load_rows(data_path)

    # 2. ANALYZE (deterministic)
    analyzer = FunnelAnalyzer(
        stages=cfg["stages"],
        segment_dimensions=cfg.get("segment_dimensions", []),
        funnel_name=cfg.get("funnel_name", "Funnel"),
    )
    analysis = analyzer.analyze(rows)

    # 2b. VERIFY the math before trusting it
    problems = FunnelAnalyzer.verify(analysis)

    # 3 + 4. SYNTHESIZE -> REPORT
    out = synthesize_report(analysis, client=client)

    return {
        "report_markdown": out["report_markdown"],
        "analysis": analysis,
        "verification": {"passed": not problems, "problems": problems},
        "used_llm": out["used_llm"],
        "model": out["model"],
    }
