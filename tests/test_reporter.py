import re
from pathlib import Path

from analyst_agent.runner import run_question


def _write_csv(tmp_path: Path) -> Path:
    data_path = tmp_path / "sample.csv"
    data_path.write_text("category,value\nA,10\nB,12\n")
    return data_path


def _section_content(report_text: str, heading: str) -> str:
    pattern = rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, report_text, re.S)
    assert match, f"Missing section: {heading}"
    return match.group(1).strip()


def test_report_contains_required_sections_and_findings(tmp_path):
    data_path = _write_csv(tmp_path)
    report_path = tmp_path / "reports" / "latest.md"
    trace_path = tmp_path / "reports" / "trace.jsonl"
    artifacts_dir = tmp_path / "artifacts"

    run_question(
        question="Which category leads?",
        data_path=str(data_path),
        report_path=str(report_path),
        trace_path=str(trace_path),
        artifacts_dir=str(artifacts_dir),
    )

    report_text = report_path.read_text()

    executive = _section_content(report_text, "Executive Summary")
    assert len([line for line in executive.splitlines() if line.startswith("- ")]) == 3

    key_findings = _section_content(report_text, "Key Findings")
    finding_lines = [line for line in key_findings.splitlines() if line.startswith("- F")]
    assert 2 <= len(finding_lines) <= 5
    for line in finding_lines:
        assert "artifacts/tables/query_" in line
        assert "Trace query id" in line

    recommendations = _section_content(report_text, "Recommendations")
    recommendation_lines = [line for line in recommendations.splitlines() if line.startswith("- ")]
    finding_ids = set(re.findall(r"F\d+", key_findings))
    assert 3 <= len(recommendation_lines) <= 5
    for line in recommendation_lines:
        referenced = set(re.findall(r"F\d+", line))
        assert referenced
        assert referenced.issubset(finding_ids)

    for section in [
        "Diagnostics",
        "Recommendations",
        "Appendix",
    ]:
        _section_content(report_text, section)
