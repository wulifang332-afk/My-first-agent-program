"""Evaluation harness for analyst_agent."""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from analyst_agent.runner import run_question


@dataclass(frozen=True)
class EvalQuestion:
    question_id: str
    question: str


@dataclass(frozen=True)
class EvalResult:
    question_id: str
    question: str
    status: str
    runtime_ms: int
    sql_count: int
    chart_count: int
    report_path: str
    trace_path: str
    error: str


def load_questions(path: str) -> List[EvalQuestion]:
    questions: List[EvalQuestion] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            question_id = payload.get("question_id") or payload.get("id")
            question = payload.get("question")
            if isinstance(question_id, str) and isinstance(question, str):
                questions.append(EvalQuestion(question_id=question_id, question=question))
    return questions


def _count_markdown_section_items(markdown: str, section: str) -> int:
    header = f"## {section}"
    start_index = markdown.find(header)
    if start_index == -1:
        return 0
    remainder = markdown[start_index + len(header) :]
    next_header = remainder.find("\n## ")
    section_text = remainder if next_header == -1 else remainder[:next_header]
    lines = [line.strip() for line in section_text.splitlines()]
    return len([line for line in lines if line.startswith("- ")])


def count_findings(markdown: str) -> int:
    header = "## Key Findings"
    start_index = markdown.find(header)
    if start_index == -1:
        return 0
    remainder = markdown[start_index + len(header) :]
    next_header = remainder.find("\n## ")
    section_text = remainder if next_header == -1 else remainder[:next_header]
    lines = [line.strip() for line in section_text.splitlines()]
    return len([line for line in lines if line.startswith("- F")])


def count_recommendations(markdown: str) -> int:
    return _count_markdown_section_items(markdown, "Recommendations")


def _collect_trace_counts(trace_path: str) -> Tuple[int, int, List[str]]:
    sql_count = 0
    chart_count = 0
    chart_paths: List[str] = []
    with open(trace_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            event_type = entry.get("event_type")
            payload = entry.get("payload", {})
            if event_type == "sql_call":
                sql_count += 1
            if event_type == "chart_saved":
                chart_count += 1
                chart_path = payload.get("chart_path")
                if isinstance(chart_path, str):
                    chart_paths.append(chart_path)
    return sql_count, chart_count, chart_paths


def evaluate_report(report_path: str, trace_path: str) -> Tuple[bool, str, int, int]:
    sql_count, chart_count, chart_paths = _collect_trace_counts(trace_path)
    errors: List[str] = []

    if sql_count < 1:
        errors.append("sql_count < 1")
    if chart_count < 1:
        errors.append("chart_count < 1")
    if not Path(report_path).exists():
        errors.append("report_missing")
    if Path(report_path).exists():
        report_text = Path(report_path).read_text(encoding="utf-8")
        findings_count = count_findings(report_text)
        recommendations_count = count_recommendations(report_text)
        if findings_count < 3:
            errors.append("findings_count < 3")
        if recommendations_count < 3:
            errors.append("recommendations_count < 3")
    for chart_path in chart_paths:
        if not Path(chart_path).exists():
            errors.append(f"chart_missing:{chart_path}")
    return (not errors), "; ".join(errors), sql_count, chart_count


def _write_results_csv(results_path: str, results: Iterable[EvalResult]) -> None:
    Path(results_path).parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "question_id",
                "question",
                "status",
                "runtime_ms",
                "sql_count",
                "chart_count",
                "report_path",
                "trace_path",
                "error",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.question_id,
                    result.question,
                    result.status,
                    result.runtime_ms,
                    result.sql_count,
                    result.chart_count,
                    result.report_path,
                    result.trace_path,
                    result.error,
                ]
            )


def _run_single_question(
    question: EvalQuestion,
    data_path: str,
    output_dir: Path,
) -> EvalResult:
    question_dir = output_dir / question.question_id
    question_dir.mkdir(parents=True, exist_ok=True)
    report_path = question_dir / "report.md"
    trace_path = question_dir / "trace.jsonl"
    artifacts_dir = question_dir / "artifacts"

    start_time = time.perf_counter()
    error_message = ""
    sql_count = 0
    chart_count = 0
    status = "pass"

    try:
        run_question(
            question=question.question,
            data_path=data_path,
            report_path=str(report_path),
            trace_path=str(trace_path),
            artifacts_dir=str(artifacts_dir),
        )
        passed, error_message, sql_count, chart_count = evaluate_report(
            report_path=str(report_path),
            trace_path=str(trace_path),
        )
        if not passed:
            status = "fail"
    except Exception as exc:
        status = "fail"
        error_message = str(exc)
    runtime_ms = int((time.perf_counter() - start_time) * 1000)
    return EvalResult(
        question_id=question.question_id,
        question=question.question,
        status=status,
        runtime_ms=runtime_ms,
        sql_count=sql_count,
        chart_count=chart_count,
        report_path=str(report_path),
        trace_path=str(trace_path),
        error=error_message,
    )


def _print_summary_table(results: Iterable[EvalResult]) -> None:
    headers = [
        "question_id",
        "status",
        "runtime_ms",
        "sql_count",
        "chart_count",
        "report_path",
        "trace_path",
        "error",
    ]
    rows = [
        [
            result.question_id,
            result.status,
            str(result.runtime_ms),
            str(result.sql_count),
            str(result.chart_count),
            result.report_path,
            result.trace_path,
            result.error,
        ]
        for result in results
    ]

    column_widths = [
        max(len(headers[idx]), *(len(row[idx]) for row in rows)) if rows else len(headers[idx])
        for idx in range(len(headers))
    ]

    def format_row(values: List[str]) -> str:
        return " | ".join(value.ljust(column_widths[idx]) for idx, value in enumerate(values))

    divider = "-+-".join("-" * width for width in column_widths)
    print(format_row(headers))
    print(divider)
    for row in rows:
        print(format_row(row))


def run_eval(
    data_path: str,
    output_dir: str,
    questions_path: str = "eval/questions.jsonl",
) -> bool:
    questions = load_questions(questions_path)
    run_dir = Path(output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    results: List[EvalResult] = []
    for question in questions:
        results.append(_run_single_question(question, data_path=data_path, output_dir=run_dir))

    results_path = str(Path(output_dir) / "results.csv")
    _write_results_csv(results_path, results)
    _print_summary_table(results)
    return all(result.status == "pass" for result in results)
