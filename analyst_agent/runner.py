"""Core analysis pipeline for the MVP."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import List, Tuple

import pandas as pd

from analyst_agent.reporter import generate_report
from analyst_agent.tools import PythonChartTool, SQLResult, SQLTool
from analyst_agent.tracing import TraceLogger


@dataclass
class AnalysisArtifacts:
    plan: List[str]
    sql: str
    result_df: pd.DataFrame
    chart_path: str
    table_path: str
    preview_markdown: str
    recommendations: List[str]


def _read_headers(data_path: str) -> List[str]:
    with open(data_path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader)


def _infer_columns(data_path: str) -> Tuple[List[str], List[str]]:
    df = pd.read_csv(data_path)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = [col for col in df.columns if col not in numeric_cols]
    return numeric_cols, categorical_cols


def _build_plan(question: str, headers: List[str]) -> List[str]:
    return [
        f"Review columns available: {', '.join(headers)}.",
        "Aggregate key metrics with SQL in DuckDB.",
        "Visualize the most relevant metric with a simple chart.",
        "Summarize findings and provide recommendations.",
    ]


def _build_sql(numeric_cols: List[str], categorical_cols: List[str]) -> str:
    if numeric_cols and categorical_cols:
        metric = numeric_cols[0]
        group = categorical_cols[0]
        return (
            f"SELECT {group} AS category, "
            f"ROUND(AVG({metric}), 2) AS avg_{metric}, "
            f"SUM({metric}) AS total_{metric} "
            "FROM data "
            f"GROUP BY {group} "
            f"ORDER BY avg_{metric} DESC;"
        )
    if numeric_cols:
        metric = numeric_cols[0]
        return f"SELECT ROUND(AVG({metric}), 2) AS avg_{metric}, SUM({metric}) AS total_{metric} FROM data;"
    return "SELECT COUNT(*) AS row_count FROM data;"


def _build_recommendations(result_df: pd.DataFrame) -> List[str]:
    recommendations = [
        "Double down on the strongest-performing category based on average metrics.",
        "Investigate drivers behind lower-performing categories and run targeted experiments.",
        "Monitor trends weekly and refresh the analysis with updated data.",
    ]
    if "category" in result_df.columns and not result_df.empty:
        top_category = result_df.iloc[0]["category"]
        recommendations[0] = (
            f"Prioritize the {top_category} category, which leads on average performance."
        )
    return recommendations


def run_question(
    question: str,
    data_path: str,
    report_path: str = "reports/latest.md",
    trace_path: str = "reports/trace.jsonl",
    artifacts_dir: str = "artifacts",
) -> AnalysisArtifacts:
    trace = TraceLogger(path=trace_path)
    try:
        headers = _read_headers(data_path)
        numeric_cols, categorical_cols = _infer_columns(data_path)
        plan = _build_plan(question, headers)
        trace.log(
            "plan",
            {
                "question": question,
                "data_path": data_path,
                "headers": headers,
                "numeric_cols": numeric_cols,
                "categorical_cols": categorical_cols,
                "steps": plan,
            },
        )

        sql = _build_sql(numeric_cols, categorical_cols)
        sql_tool = SQLTool(data_path=data_path, artifacts_dir=artifacts_dir)
        sql_result: SQLResult = sql_tool.run_query(sql)
        trace.log(
            "sql_call",
            {
                "query_id": sql_result.query_id,
                "query": sql,
                "prepared_sql": sql_result.sql,
                "table": sql_tool.table_name,
            },
        )
        trace.log(
            "sql_result",
            {
                "query_id": sql_result.query_id,
                "row_count": len(sql_result.dataframe),
                "table_path": sql_result.table_path,
            },
        )

        chart_tool = PythonChartTool(artifacts_dir=artifacts_dir)
        chart_result = chart_tool.create_chart(sql_result.dataframe)
        trace.log(
            "chart_call",
            {
                "chart_id": chart_result.chart_id,
                "query_id": sql_result.query_id,
                "columns": list(sql_result.dataframe.columns),
            },
        )
        trace.log(
            "chart_saved",
            {"chart_id": chart_result.chart_id, "chart_path": chart_result.chart_path},
        )

        recommendations = _build_recommendations(sql_result.dataframe)

        artifacts = AnalysisArtifacts(
            plan=plan,
            sql=sql_result.sql,
            result_df=sql_result.dataframe,
            chart_path=chart_result.chart_path,
            table_path=sql_result.table_path,
            preview_markdown=sql_result.preview_markdown,
            recommendations=recommendations,
        )
        trace.flush()
        generate_report(
            report_path=report_path,
            trace_path=trace_path,
            data_path=data_path,
            question=question,
        )
        trace.log("report_written", {"report_path": report_path})

        return artifacts
    except Exception as exc:  # pragma: no cover - defensive logging
        trace.log("error", {"message": str(exc)})
        raise
    finally:
        trace.flush()
