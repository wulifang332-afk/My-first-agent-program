"""Core analysis pipeline for the MVP."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import duckdb
import matplotlib
import pandas as pd

from analyst_agent.tracing import TraceLogger

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


@dataclass
class AnalysisArtifacts:
    plan: List[str]
    sql: str
    result_df: pd.DataFrame
    chart_path: str
    recommendations: List[str]


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


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


def _build_chart(result_df: pd.DataFrame, chart_path: str) -> None:
    _ensure_parent(chart_path)
    plt.figure(figsize=(6, 4))
    if "category" in result_df.columns and len(result_df.columns) >= 2:
        metric_col = result_df.columns[1]
        plt.bar(result_df["category"], result_df[metric_col], color="#4C78A8")
        plt.title(f"{metric_col} by category")
        plt.xlabel("Category")
        plt.ylabel(metric_col)
    else:
        value = result_df.iloc[0, 0] if not result_df.empty else 0
        plt.bar(["value"], [value], color="#4C78A8")
        plt.title("Summary metric")
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()


def _write_report(
    report_path: str,
    question: str,
    artifacts: AnalysisArtifacts,
) -> None:
    _ensure_parent(report_path)
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("# Latest Analysis Report\n\n")
        handle.write(f"**Question:** {question}\n\n")
        handle.write("## Plan\n")
        for step in artifacts.plan:
            handle.write(f"- {step}\n")
        handle.write("\n## SQL\n")
        handle.write("```sql\n")
        handle.write(f"{artifacts.sql}\n")
        handle.write("```\n\n")
        handle.write("## Results\n")
        handle.write(artifacts.result_df.to_markdown(index=False))
        handle.write("\n\n")
        handle.write("## Chart\n")
        handle.write(f"{artifacts.chart_path}\n\n")
        handle.write("## Recommendations\n")
        for recommendation in artifacts.recommendations:
            handle.write(f"- {recommendation}\n")


def run_question(
    question: str,
    data_path: str,
    report_path: str = "reports/latest.md",
    trace_path: str = "reports/trace.jsonl",
) -> AnalysisArtifacts:
    trace = TraceLogger(path=trace_path)
    trace.log("start", {"question": question, "data_path": data_path})

    headers = _read_headers(data_path)
    trace.log("data_headers", {"headers": headers})

    numeric_cols, categorical_cols = _infer_columns(data_path)
    trace.log(
        "data_inference",
        {"numeric_cols": numeric_cols, "categorical_cols": categorical_cols},
    )

    plan = _build_plan(question, headers)
    trace.log("plan_built", {"plan": plan})

    sql = _build_sql(numeric_cols, categorical_cols)
    trace.log("sql_built", {"sql": sql})

    connection = duckdb.connect()
    trace.log("duckdb_connect", {})
    connection.execute("CREATE OR REPLACE TABLE data AS SELECT * FROM read_csv_auto(?)", [data_path])
    result_df = connection.execute(sql).df()
    trace.log("sql_executed", {"row_count": len(result_df)})

    chart_path = "charts/latest.png"
    _build_chart(result_df, chart_path)
    trace.log("chart_saved", {"chart_path": chart_path})

    recommendations = _build_recommendations(result_df)
    trace.log("recommendations", {"recommendations": recommendations})

    artifacts = AnalysisArtifacts(
        plan=plan,
        sql=sql,
        result_df=result_df,
        chart_path=chart_path,
        recommendations=recommendations,
    )
    _write_report(report_path, question, artifacts)
    trace.log("report_written", {"report_path": report_path})

    trace.flush()
    return artifacts
