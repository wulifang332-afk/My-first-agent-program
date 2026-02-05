from pathlib import Path

from analyst_agent.runner import run_question


def _write_csv(tmp_path: Path) -> Path:
    data_path = tmp_path / "sample.csv"
    data_path.write_text("category,value\nA,10\nB,12\n")
    return data_path


def test_runner_creates_artifacts_and_report(tmp_path):
    data_path = _write_csv(tmp_path)
    report_path = tmp_path / "reports" / "latest.md"
    trace_path = tmp_path / "reports" / "trace.jsonl"
    artifacts_dir = tmp_path / "artifacts"

    artifacts = run_question(
        question="Which category leads?",
        data_path=str(data_path),
        report_path=str(report_path),
        trace_path=str(trace_path),
        artifacts_dir=str(artifacts_dir),
    )

    assert (artifacts_dir / "tables").exists()
    assert (artifacts_dir / "charts").exists()
    assert report_path.exists()
    assert Path(artifacts.chart_path).exists()
