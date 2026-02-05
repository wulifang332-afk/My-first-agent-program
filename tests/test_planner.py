import pytest

from analyst_agent.planner import plan_question


QUESTIONS = [
    "Show the revenue trend over time by month.",
    "Compare conversion rate vs last quarter for mobile vs desktop.",
    "Breakdown of orders by country and channel.",
    "What does the funnel look like from signup to purchase?",
    "Any anomaly in daily active users this week?",
    "Attribution of sales to marketing channels.",
    "Give me a summary of total sessions.",
    "How did churn change over the last year?",
    "Compare product A versus product B revenue.",
    "Segment retention by plan tier.",
]


def _assert_schema(plan: dict) -> None:
    assert set(plan.keys()) == {
        "intent",
        "metrics",
        "dimensions",
        "time_window",
        "hypotheses",
        "actions",
    }
    assert isinstance(plan["intent"], str)
    assert isinstance(plan["metrics"], list)
    assert all(isinstance(item, str) for item in plan["metrics"])
    assert isinstance(plan["dimensions"], list)
    assert all(isinstance(item, str) for item in plan["dimensions"])
    assert isinstance(plan["time_window"], dict)
    assert set(plan["time_window"].keys()) == {"start", "end", "grain"}
    assert isinstance(plan["hypotheses"], list)
    assert 2 <= len(plan["hypotheses"]) <= 3
    assert all(isinstance(item, str) for item in plan["hypotheses"])
    assert isinstance(plan["actions"], list)
    assert all(isinstance(item, dict) for item in plan["actions"])


def test_planner_schema_and_determinism():
    for question in QUESTIONS:
        first = plan_question(question)
        second = plan_question(question)
        _assert_schema(first)
        assert first == second


@pytest.mark.parametrize(
    "question,expected_intent",
    [
        ("Show the revenue trend over time.", "trend"),
        ("Compare A vs B performance.", "comparison"),
        ("Breakdown revenue by channel.", "segmentation"),
        ("What is the conversion funnel by step?", "funnel"),
        ("Spot an anomaly in daily users.", "anomaly"),
        ("Attribution of revenue to campaigns.", "attribution"),
        ("Give me a summary of total orders.", "summary"),
    ],
)
def test_intent_classification(question, expected_intent):
    assert plan_question(question)["intent"] == expected_intent
