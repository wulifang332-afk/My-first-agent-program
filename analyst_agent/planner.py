"""Rule-based planner for converting questions into structured analysis plans."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TimeWindow:
    start: str | None
    end: str | None
    grain: str | None

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "grain": self.grain}


INTENT_KEYWORDS = {
    "trend": ["trend", "over time", "over the", "growth", "increase", "decrease"],
    "comparison": ["compare", "vs", "versus", "difference", "relative"],
    "funnel": ["funnel", "conversion", "drop-off", "step"],
    "segmentation": ["breakdown", "segment", "by ", "group by", "grouped"],
    "anomaly": ["anomaly", "spike", "dip", "outlier", "unexpected"],
    "attribution": ["attribution", "driver", "cause", "impact", "contribution"],
}

METRIC_KEYWORDS = {
    "revenue": ["revenue", "sales"],
    "users": ["users", "active users"],
    "sessions": ["sessions", "visits"],
    "orders": ["orders", "purchases"],
    "conversion_rate": ["conversion rate", "conversion"],
    "churn": ["churn"],
    "retention": ["retention"],
    "clicks": ["clicks"],
    "signups": ["signups", "registrations"],
}

DIMENSION_KEYWORDS = {
    "country": ["country", "countries"],
    "region": ["region"],
    "device": ["device", "mobile", "desktop"],
    "channel": ["channel", "source", "campaign"],
    "product": ["product"],
    "category": ["category"],
    "plan": ["plan", "tier"],
    "segment": ["segment", "cohort"],
}

GRAIN_KEYWORDS = {
    "daily": ["daily", "day"],
    "weekly": ["weekly", "week"],
    "monthly": ["monthly", "month"],
    "quarterly": ["quarterly", "quarter"],
    "yearly": ["yearly", "year"],
}


def plan_question(question: str) -> dict:
    """Plan a question into a deterministic, structured JSON-like dict."""

    normalized = _normalize(question)
    intent = _detect_intent(normalized)
    metrics = _detect_metrics(normalized)
    dimensions = _detect_dimensions(normalized, intent)
    time_window = _detect_time_window(normalized)
    hypotheses = _build_hypotheses(intent)
    actions = _build_actions(intent, metrics, dimensions, time_window)
    return {
        "intent": intent,
        "metrics": metrics,
        "dimensions": dimensions,
        "time_window": time_window.to_dict(),
        "hypotheses": hypotheses,
        "actions": actions,
    }


def _normalize(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def _detect_intent(normalized: str) -> str:
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return intent
    if " by " in normalized:
        return "segmentation"
    return "summary"


def _detect_metrics(normalized: str) -> list[str]:
    metrics: list[str] = []
    for metric, keywords in METRIC_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            metrics.append(metric)
    if not metrics:
        metrics.append("count")
    return metrics


def _detect_dimensions(normalized: str, intent: str) -> list[str]:
    dimensions: list[str] = []
    for dimension, keywords in DIMENSION_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            dimensions.append(dimension)
    if intent == "trend" and "date" not in dimensions:
        dimensions.append("date")
    return dimensions


def _detect_time_window(normalized: str) -> TimeWindow:
    dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", normalized)
    start = dates[0] if dates else None
    end = dates[1] if len(dates) > 1 else None
    grain = None
    for grain_name, keywords in GRAIN_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            grain = grain_name
            break
    return TimeWindow(start=start, end=end, grain=grain)


def _build_hypotheses(intent: str) -> list[str]:
    hypothesis_bank = {
        "trend": [
            "Seasonality or calendar effects are driving the trend.",
            "Changes in acquisition volume are influencing the metric.",
        ],
        "comparison": [
            "Differences in user mix explain the gap between cohorts.",
            "Pricing or promotion changes caused the variance.",
        ],
        "segmentation": [
            "Customer behavior varies significantly by segment.",
            "Operational differences across segments drive performance changes.",
        ],
        "funnel": [
            "A specific funnel step has a higher-than-expected drop-off.",
            "Traffic quality differences are affecting conversion rates.",
        ],
        "anomaly": [
            "A data quality issue created the observed spike or dip.",
            "A one-time event shifted the metric temporarily.",
        ],
        "attribution": [
            "One channel contributes disproportionately to the outcome.",
            "Recent campaigns shifted attribution mix toward a single driver.",
        ],
        "summary": [
            "Overall performance is driven by the largest customer cohorts.",
            "Top-performing segments dominate the aggregate metric.",
        ],
    }
    return hypothesis_bank[intent][:2]


def _build_actions(
    intent: str,
    metrics: list[str],
    dimensions: list[str],
    time_window: TimeWindow,
) -> list[dict]:
    query = _build_query(metrics, dimensions, time_window)
    actions: list[dict] = [
        {"tool": "SQLTool", "params": {"query": query, "limit": 200}},
    ]
    if intent in {"trend", "comparison", "segmentation"}:
        x_axis = dimensions[0] if dimensions else "category"
        y_axis = _metric_alias(metrics[0])
        kind = "line" if intent == "trend" else "bar"
        actions.append(
            {
                "tool": "PythonChartTool",
                "params": {"kind": kind, "x": x_axis, "y": y_axis},
            }
        )
    return actions


def _build_query(metrics: list[str], dimensions: list[str], time_window: TimeWindow) -> str:
    metric_expressions = [_metric_expression(metric) for metric in metrics]
    select_parts = []
    if dimensions:
        select_parts.extend(dimensions)
    select_parts.extend(metric_expressions)
    select_clause = ", ".join(select_parts)
    query = f"SELECT {select_clause} FROM data"
    where_clauses = _build_time_filters(time_window)
    if where_clauses:
        query = f"{query} WHERE {' AND '.join(where_clauses)}"
    if dimensions:
        query = f"{query} GROUP BY {', '.join(dimensions)}"
    return query


def _build_time_filters(time_window: TimeWindow) -> list[str]:
    clauses: list[str] = []
    if time_window.start:
        clauses.append(f"date >= '{time_window.start}'")
    if time_window.end:
        clauses.append(f"date <= '{time_window.end}'")
    return clauses


def _metric_expression(metric: str) -> str:
    if metric == "count":
        return "COUNT(*) AS count"
    return f"SUM({metric}) AS {_metric_alias(metric)}"


def _metric_alias(metric: str) -> str:
    return metric
