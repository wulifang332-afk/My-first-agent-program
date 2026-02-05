import subprocess
import sys
from pathlib import Path


def test_cli_run_smoke(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    data_path = repo_root / "data" / "sample.csv"
    report_path = tmp_path / "report.md"
    trace_path = tmp_path / "trace.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "analyst_agent",
            "run",
            "--question",
            "Which region has the highest average units?",
            "--data",
            str(data_path),
            "--report-path",
            str(report_path),
            "--trace-path",
            str(trace_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
