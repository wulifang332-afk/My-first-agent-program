"""Deterministic markdown reporter for analysis artifacts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class TraceQuery:
    query_id: int
    sql: str
    table_path: str
    chart_path: Optional[str] = None


@dataclass(frozen=True)
class TraceParameters:
    data_path: str
    question: str


class ReportGenerationError(RuntimeError):
    """Raised when required artifacts for the report are missing."""


def _load_trace_entries(trace_path: str) -> List[Dict[str, object]]:
    trace_file = Path(trace_path)
    if not trace_file.exists():
        raise ReportGenerationError(f"Trace file not found: {trace_path}")
    entries: List[Dict[str, object]] = []
    with open(trace_file, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                entries.append(json.loads(line))
    if not entries:
        raise ReportGenerationError(f"Trace file is empty: {trace_path}")
    return entries


def _extract_parameters(entries: Iterable[Dict[str, object]]) -> Optional[TraceParameters]:
    for entry in entries:
        if entry.get("event_type") == "plan":
            payload = entry.get("payload", {})
            data_path = payload.get("data_path")
            question = payload.get("question")
            if isinstance(data_path, str) and isinstance(question, str):
                return TraceParameters(data_path=data_path, question=question)
    return None


def _extract_queries(entries: Iterable[Dict[str, object]]) -> List[TraceQuery]:
    sql_by_id: Dict[int, str] = {}
    table_by_id: Dict[int, str] = {}
    chart_by_id: Dict[int, str] = {}
    chart_query_map: Dict[int, int] = {}

    for entry in entries:
        event_type = entry.get("event_type")
        payload = entry.get("payload", {})
        if event_type == "sql_call":
            query_id = payload.get("query_id")
            if isinstance(query_id, int):
                sql = payload.get("prepared_sql") or payload.get("query")
                if isinstance(sql, str):
                    sql_by_id[query_id] = sql
        if event_type == "sql_result":
            query_id = payload.get("query_id")
            table_path = payload.get("table_path")
            if isinstance(query_id, int) and isinstance(table_path, str):
                table_by_id[query_id] = table_path
        if event_type == "chart_call":
            chart_id = payload.get("chart_id")
            query_id = payload.get("query_id")
            if isinstance(chart_id, int) and isinstance(query_id, int):
                chart_query_map[chart_id] = query_id
        if event_type == "chart_saved":
            chart_id = payload.get("chart_id")
            chart_path = payload.get("chart_path")
            if isinstance(chart_id, int) and isinstance(chart_path, str):
                chart_by_id[chart_id] = chart_path

    queries: List[TraceQuery] = []
    for query_id in sorted(table_by_id.keys()):
        sql = sql_by_id.get(query_id, "")
        table_path = table_by_id[query_id]
        chart_path = None
        for chart_id, mapped_query in chart_query_map.items():
            if mapped_query == query_id and chart_id in chart_by_id:
                chart_path = chart_by_id[chart_id]
                break
        queries.append(
            TraceQuery(
                query_id=query_id,
                sql=sql,
                table_path=table_path,
                chart_path=chart_path,
            )
        )

    if not queries:
        raise ReportGenerationError("No SQL results found in trace to build findings.")
    return queries


def _extract_planner_output(entries: Iterable[Dict[str, object]]) -> Optional[Dict[str, object]]:
    for entry in entries:
        if entry.get("event_type") == "planner":
            payload = entry.get("payload")
            if isinstance(payload, dict):
                return payload
    for entry in entries:
        if entry.get("event_type") == "plan":
            payload = entry.get("payload", {})
            planner_output = payload.get("planner_output")
            if isinstance(planner_output, dict):
                return planner_output
    return None


def _display_artifact_path(path: Path) -> str:
    path_str = path.as_posix()
    marker = "artifacts/"
    marker_index = path_str.rfind(marker)
    if marker_index >= 0:
        return path_str[marker_index:]
    return path_str


def _relative_link(report_path: str, target_path: str) -> str:
    report_dir = Path(report_path).parent
    return Path(os.path.relpath(target_path, start=report_dir)).as_posix()


def _validate_artifacts(queries: Iterable[TraceQuery]) -> None:
    missing: List[str] = []
    for query in queries:
        if not Path(query.table_path).exists():
            missing.append(query.table_path)
        if query.chart_path and not Path(query.chart_path).exists():
            missing.append(query.chart_path)
    if missing:
        missing_list = ", ".join(missing)
        raise ReportGenerationError(f"Missing required artifacts: {missing_list}")


def _build_findings(
    queries: List[TraceQuery],
    report_path: str,
) -> Tuple[List[str], List[TraceQuery]]:
    findings: List[str] = []
    queries_for_findings = queries[:5]

    def build_finding_text(finding_id: str, query: TraceQuery, detail: str) -> str:
        table_label = _display_artifact_path(Path(query.table_path))
        table_link = _relative_link(report_path, query.table_path)
        table_ref = f"[{table_label}]({table_link})"
        chart_ref = ""
        if query.chart_path:
            chart_label = _display_artifact_path(Path(query.chart_path))
            chart_link = _relative_link(report_path, query.chart_path)
            chart_ref = f" Chart: [{chart_label}]({chart_link})."
        return (
            f"{finding_id}: {detail} "
            f"Table: {table_ref}. Trace query id: {query.query_id}."
            f"{chart_ref}"
        )

    if len(queries_for_findings) >= 3:
        for idx, query in enumerate(queries_for_findings, start=1):
            dataframe = pd.read_csv(query.table_path)
            detail = (
                f"Query {query.query_id} returned {len(dataframe)} row(s) "
                f"across {len(dataframe.columns)} column(s)."
            )
            findings.append(build_finding_text(f"F{idx}", query, detail))
        return findings, queries_for_findings

    query = queries_for_findings[0]
    dataframe = pd.read_csv(query.table_path)
    detail_primary = (
        f"Query {query.query_id} returned {len(dataframe)} row(s) "
        f"across {len(dataframe.columns)} column(s)."
    )
    findings.append(build_finding_text("F1", query, detail_primary))

    sample_detail = "The first row contains no data."
    if not dataframe.empty:
        first_row = dataframe.iloc[0].to_dict()
        sample_pairs = ", ".join(f"{key}={value}" for key, value in first_row.items())
        sample_detail = f"Sample of the first row: {sample_pairs}."
    findings.append(build_finding_text("F2", query, sample_detail))

    columns_detail = (
        "The table includes the following columns: "
        f"{', '.join(str(col) for col in dataframe.columns)}."
    )
    findings.append(build_finding_text("F3", query, columns_detail))

    return findings, queries_for_findings


def _render_table_preview(csv_path: str, max_rows: int) -> str:
    dataframe = pd.read_csv(csv_path)
    preview = dataframe.head(max_rows).to_markdown(index=False)
    return preview


def _render_schema_snapshot(data_path: str) -> str:
    dataframe = pd.read_csv(data_path)
    schema = pd.DataFrame(
        [{"column": name, "type": str(dtype)} for name, dtype in dataframe.dtypes.items()]
    )
    return schema.to_markdown(index=False)


def generate_report(
    report_path: str,
    trace_path: str,
    data_path: Optional[str] = None,
    question: Optional[str] = None,
    preview_rows: int = 5,
) -> None:
    """Generate the latest markdown report from existing artifacts and trace logs."""
    entries = _load_trace_entries(trace_path)
    trace_params = _extract_parameters(entries)
    if trace_params:
        data_path = data_path or trace_params.data_path
        question = question or trace_params.question
    if not data_path or not question:
        raise ReportGenerationError("Report generation requires data_path and question.")

    queries = _extract_queries(entries)
    planner_output = _extract_planner_output(entries)
    _validate_artifacts(queries)
    findings, referenced_queries = _build_findings(queries, report_path)

    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, "w", encoding="utf-8") as handle:
        handle.write("# Latest Analysis Report\n\n")
        handle.write("## Executive Summary\n")
        handle.write(f"- Analyzed {len(queries)} query result(s) from artifacts.\n")
        handle.write(
            f"- Generated {sum(1 for query in queries if query.chart_path)} chart(s) for visualization.\n"
        )
        handle.write("- Report compiled deterministically from trace logs and artifacts.\n\n")

        handle.write("## Key Findings\n")
        for finding in findings:
            handle.write(f"- {finding}\n")
        handle.write("\n")

        handle.write("## Planner Summary\n")
        if planner_output:
            intent = planner_output.get("intent")
            metrics = planner_output.get("metrics")
            dimensions = planner_output.get("dimensions")
            if isinstance(intent, str):
                handle.write(f"- Intent: {intent}\n")
            if isinstance(metrics, list):
                handle.write(f"- Metrics: {', '.join(str(metric) for metric in metrics)}\n")
            if isinstance(dimensions, list):
                handle.write(
                    f"- Dimensions: {', '.join(str(dimension) for dimension in dimensions)}\n"
                )
        else:
            handle.write("- Intent: unavailable\n")
        handle.write("\n")

        handle.write("## Diagnostics\n")
        for query in referenced_queries:
            table_label = _display_artifact_path(Path(query.table_path))
            handle.write(f"### Table Preview: {table_label}\n")
            handle.write(_render_table_preview(query.table_path, preview_rows))
            handle.write("\n\n")
        handle.write("### Charts\n")
        for query in referenced_queries:
            if query.chart_path:
                chart_label = _display_artifact_path(Path(query.chart_path))
                chart_link = _relative_link(report_path, query.chart_path)
                handle.write(f"- [{chart_label}]({chart_link})\n")
        handle.write("\n")

        handle.write("## Recommendations\n")
        recommendation_targets = [f"F{idx}" for idx in range(1, len(findings) + 1)]
        handle.write(
            f"- Validate the leading trend highlighted in {recommendation_targets[0]} with follow-up analysis.\n"
        )
        handle.write(
            f"- Prioritize data quality checks for metrics underpinning {recommendation_targets[-1]}.\n"
        )
        handle.write(
            f"- Share results with stakeholders and align next steps based on {recommendation_targets[0]}.\n"
        )
        handle.write("\n")

        handle.write("## Appendix\n")
        handle.write("### SQL Queries\n")
        for query in queries:
            handle.write(f"#### Query {query.query_id}\n")
            handle.write("```sql\n")
            handle.write(f"{query.sql}\n")
            handle.write("```\n\n")

        handle.write("### Parameters\n")
        handle.write(f"- Data path: {data_path}\n")
        handle.write(f"- Question: {question}\n\n")

        handle.write("### Schema Snapshot\n")
        handle.write(_render_schema_snapshot(data_path))
        handle.write("\n\n")

        trace_label = Path(trace_path).as_posix()
        trace_link = _relative_link(report_path, trace_path)
        handle.write("### Trace\n")
        handle.write(f"- Trace file: [{trace_label}]({trace_link})\n")
