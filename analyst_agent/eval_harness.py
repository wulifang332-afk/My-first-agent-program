"""Evaluation harness for analyst_agent."""

from __future__ import annotations

from pathlib import Path
from typing import List

from analyst_agent.runner import run_question


def run_eval(data_path: str, output_dir: str) -> bool:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    questions: List[str] = [
        "Which region has the highest average units?",
        "Summarize overall performance across categories.",
    ]

    success = True
    for idx, question in enumerate(questions, start=1):
        report_path = str(Path(output_dir) / f"report_{idx}.md")
        trace_path = str(Path(output_dir) / f"trace_{idx}.jsonl")
        artifacts = run_question(
            question=question,
            data_path=data_path,
            report_path=report_path,
            trace_path=trace_path,
        )
        if not Path(report_path).exists() or not Path(artifacts.chart_path).exists():
            success = False

    return success
