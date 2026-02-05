"""Safe tool abstractions for the analyst agent."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Iterable, Optional

import duckdb
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FORBIDDEN_SQL = (
    "CREATE",
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "COPY",
    "ATTACH",
    "DETACH",
    "PRAGMA",
)


@dataclass
class SQLResult:
    query_id: int
    sql: str
    dataframe: pd.DataFrame
    table_path: str
    preview_markdown: str


class SQLTool:
    """Run safe, single-statement SELECT queries against a CSV-loaded DuckDB table."""

    def __init__(
        self,
        data_path: str,
        table_name: str = "data",
        artifacts_dir: str = "artifacts",
        max_rows: int = 200,
    ) -> None:
        self.data_path = data_path
        self.table_name = table_name
        self.max_rows = max_rows
        self.artifacts_dir = Path(artifacts_dir)
        self._query_counter = count(1)
        self._connection = duckdb.connect()
        self._connection.execute(
            f"CREATE OR REPLACE TABLE {self.table_name} AS SELECT * FROM read_csv_auto(?)",
            [self.data_path],
        )

    def _reject_forbidden(self, query: str) -> None:
        for keyword in FORBIDDEN_SQL:
            if re.search(rf"\b{keyword}\b", query, re.IGNORECASE):
                raise ValueError(f"Forbidden SQL keyword detected: {keyword}")

    def _prepare_query(self, query: str) -> str:
        stripped = query.strip()
        if not stripped.lower().startswith("select"):
            raise ValueError("Only SELECT statements are permitted.")
        if ";" in stripped[:-1]:
            raise ValueError("Multiple SQL statements are not permitted.")

        self._reject_forbidden(stripped)

        if stripped.endswith(";"):
            stripped = stripped[:-1].strip()

        limit_match = re.search(r"\blimit\s+(\d+)\b", stripped, re.IGNORECASE)
        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > self.max_rows:
                stripped = re.sub(
                    r"\blimit\s+\d+\b",
                    f"LIMIT {self.max_rows}",
                    stripped,
                    flags=re.IGNORECASE,
                    count=1,
                )
        else:
            stripped = f"{stripped} LIMIT {self.max_rows}"
        return stripped

    def run_query(self, query: str) -> SQLResult:
        query_id = next(self._query_counter)
        prepared = self._prepare_query(query)
        dataframe = self._connection.execute(prepared).df()
        table_path = self.artifacts_dir / "tables" / f"query_{query_id}.csv"
        table_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(table_path, index=False)
        preview = dataframe.head(20).to_markdown(index=False)
        return SQLResult(
            query_id=query_id,
            sql=prepared,
            dataframe=dataframe,
            table_path=str(table_path),
            preview_markdown=preview,
        )


@dataclass
class ChartResult:
    chart_id: int
    chart_type: str
    chart_path: str


class PythonChartTool:
    """Generate charts from dataframes without arbitrary Python execution."""

    def __init__(self, artifacts_dir: str = "artifacts") -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self._chart_counter = count(1)

    def _detect_date_column(self, dataframe: pd.DataFrame) -> Optional[str]:
        for column in dataframe.columns:
            if pd.api.types.is_datetime64_any_dtype(dataframe[column]):
                return column
        for column in dataframe.columns:
            if "date" in column.lower() or "time" in column.lower():
                parsed = pd.to_datetime(dataframe[column], errors="coerce")
                if parsed.notna().any():
                    return column
        return None

    def _select_numeric_column(self, dataframe: pd.DataFrame, exclude: Iterable[str]) -> Optional[str]:
        numeric_cols = dataframe.select_dtypes(include="number").columns
        for column in numeric_cols:
            if column not in exclude:
                return column
        return None

    def create_chart(self, dataframe: pd.DataFrame) -> ChartResult:
        chart_id = next(self._chart_counter)
        chart_path = self.artifacts_dir / "charts" / f"chart_{chart_id}.png"
        chart_path.parent.mkdir(parents=True, exist_ok=True)

        plt.figure(figsize=(6, 4))
        chart_type = "bar"
        date_column = self._detect_date_column(dataframe)
        if date_column:
            metric_col = self._select_numeric_column(dataframe, exclude=[date_column])
            if metric_col:
                sorted_df = dataframe.copy()
                sorted_df[date_column] = pd.to_datetime(sorted_df[date_column], errors="coerce")
                sorted_df = sorted_df.sort_values(date_column)
                plt.plot(sorted_df[date_column], sorted_df[metric_col], marker="o", color="#4C78A8")
                plt.title(f"{metric_col} over time")
                plt.xlabel(date_column)
                plt.ylabel(metric_col)
                chart_type = "line"
        if chart_type == "bar":
            if "category" in dataframe.columns:
                metric_col = self._select_numeric_column(dataframe, exclude=["category"])
                if metric_col:
                    plt.bar(dataframe["category"], dataframe[metric_col], color="#4C78A8")
                    plt.title(f"{metric_col} by category")
                    plt.xlabel("Category")
                    plt.ylabel(metric_col)
                else:
                    plt.bar(["value"], [0], color="#4C78A8")
                    plt.title("Summary metric")
            else:
                metric_col = self._select_numeric_column(dataframe, exclude=[])
                value = dataframe[metric_col].iloc[0] if metric_col and not dataframe.empty else 0
                plt.bar(["value"], [value], color="#4C78A8")
                plt.title("Summary metric")

        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()

        return ChartResult(
            chart_id=chart_id,
            chart_type=chart_type,
            chart_path=str(chart_path),
        )
