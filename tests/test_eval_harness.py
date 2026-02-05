import csv
import json
from pathlib import Path

import pytest

from analyst_agent.eval_harness import evaluate_report, load_questions, run_eval
from analyst_agent.runner import run_question


def test_questions_jsonl_has_minimum():
    questions = load_questions("eval/questions.jsonl")
    assert len(questions) >= 20
    assert len({question.question_id for question in questions}) == len(questions)


def test_load_questions_accepts_id_and_question_id(tmp_path):
    questions_path = tmp_path / "questions.jsonl"
    questions_path.write_text(
        "\n".join(
            [
                json.dumps({"id": "q1", "question": "First question."}),
                json.dumps({"question_id": "q2", "question": "Second question."}),
                json.dumps({"id": "bad", "question": 123}),
                "",
            ]
        )
    )

    questions = load_questions(str(questions_path))

    assert [question.question_id for question in questions] == ["q1", "q2"]
    assert [question.question for question in questions] == [
        "First question.",
        "Second question.",
    ]


def test_eval_produces_results_csv(tmp_path):
    questions_path = tmp_path / "questions.jsonl"
    questions_path.write_text(
        "\n".join(
            [
                json.dumps({"id": "t1", "question": "Summarize performance."}),
                json.dumps({"id": "t2", "question": "Compare revenue by region."}),
            ]
        )
        + "\n"
    )
    output_dir = tmp_path / "evals"
    run_eval(
        data_path="data/sample.csv",
        output_dir=str(output_dir),
        questions_path=str(questions_path),
    )

    results_path = output_dir / "results.csv"
    assert results_path.exists()
    with open(results_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][:3] == ["question_id", "question", "status"]
    assert rows[0][3:11] == [
        "runtime_ms",
        "sql_count",
        "chart_count",
        "findings_count",
        "reco_count",
        "golden_required",
        "golden_ok",
        "report_path",
    ]
    assert len(rows) == 3


def test_checks_fail_when_missing_requirements(tmp_path):
    report_path = tmp_path / "report.md"
    trace_path = tmp_path / "trace.jsonl"
    report_path.write_text("# Report\n")
    trace_path.write_text("")

    (
        passed,
        error,
        sql_count,
        chart_count,
        findings_count,
        reco_count,
        golden_required,
        golden_ok,
    ) = evaluate_report(
        report_path=str(report_path),
        trace_path=str(trace_path),
    )

    assert not passed
    assert "sql_count < 1" in error
    assert "chart_count < 1" in error
    assert sql_count == 0
    assert chart_count == 0
    assert findings_count == 0
    assert reco_count == 0
    assert not golden_required
    assert golden_ok


@pytest.mark.parametrize(
    ("question", "expected_intent", "expected_metrics", "expected_dimensions"),
    [
        (
            "What is the revenue trend over time by month?",
            "trend",
            "revenue",
            "date",
        ),
        ("Compare orders by region.", "comparison", "orders", "region"),
        ("Break down signups by channel.", "segmentation", "signups", "channel"),
    ],
)
def test_golden_planner_outputs_in_report(
    tmp_path,
    question,
    expected_intent,
    expected_metrics,
    expected_dimensions,
):
    data_path = Path("data/sample.csv")
    report_path = tmp_path / "report.md"
    trace_path = tmp_path / "trace.jsonl"
    artifacts_dir = tmp_path / "artifacts"

    run_question(
        question=question,
        data_path=str(data_path),
        report_path=str(report_path),
        trace_path=str(trace_path),
        artifacts_dir=str(artifacts_dir),
    )

    report_text = report_path.read_text(encoding="utf-8")
    assert f"Intent: {expected_intent}" in report_text
    assert f"Metrics: {expected_metrics}" in report_text
    assert f"Dimensions: {expected_dimensions}" in report_text
