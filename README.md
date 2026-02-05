# My-first-agent-program

## What it does

The `analyst_agent` runs a deterministic analysis pipeline that takes a natural-language question, plans the work, executes a safe SQL query in DuckDB, and produces a Markdown report. It always writes trace logs plus reproducible artifacts (tables and charts) so results can be audited end-to-end. The core run writes `reports/latest.md`, `reports/trace.jsonl`, `artifacts/tables/query_1.csv`, and `artifacts/charts/chart_1.png`, while the eval harness writes per-question outputs like `reports/evals/q01/report.md`, `reports/evals/q01/trace.jsonl`, `reports/evals/q01/artifacts/tables/query_1.csv`, and `reports/evals/q01/artifacts/charts/chart_1.png` alongside `reports/evals/results.csv`.

## Sample outputs

- Example report: [assets/example_report.md](assets/example_report.md)
- Example trace log: [assets/example_trace.jsonl](assets/example_trace.jsonl)
- Example chart: [assets/example_chart.png](assets/example_chart.png)

## Screenshots

```
TODO:
- docs/screenshots/eval_summary.png
- docs/screenshots/sample_report.png
```

## Quickstart

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run a single question:

```bash
python -m analyst_agent run --question "Which region has the highest average units?" --data data/sample.csv
```

Run the eval harness:

```bash
python -m analyst_agent eval --data data/sample.csv --output-dir reports/evals --questions eval/questions.jsonl
```

## Architecture

```
User question
   │
   ▼
Planner (analyst_agent/planner.py)
   │
   ▼
SQLTool (analyst_agent/tools.py) ─────────────┐
   │                                           │
   ▼                                           │
Artifacts: artifacts/tables/query_*.csv        │
   │                                           │
   ▼                                           │
PythonChartTool (analyst_agent/tools.py)       │
   │                                           │
   ▼                                           │
Artifacts: artifacts/charts/chart_*.png        │
   │                                           │
   ▼                                           │
Reporter (analyst_agent/reporter.py)           │
   │                                           │
   ▼                                           │
Markdown report (reports/latest.md)            │

Trace logs (reports/trace.jsonl) ──────────────┘
```

Key modules:

- `analyst_agent/runner.py` orchestrates planning, SQL execution, charting, and report generation.
- `analyst_agent/reporter.py` deterministically builds the Markdown report from trace logs and artifacts.
- `analyst_agent/eval_harness.py` runs the eval suite and records per-question metrics.
- `analyst_agent/tools.py` contains the safe SQL and charting tools.
- `analyst_agent/planner.py` provides rule-based intent/metric/dimension extraction.
- `analyst_agent/tracing.py` writes JSONL trace logs for every step.

## Evaluation

Pass criteria require at least one SQL query, one chart, three findings, and three recommendations in each report. The eval harness writes `reports/evals/results.csv` with per-question metrics: `sql_count`, `chart_count`, `findings_count`, `reco_count`, `golden_required`, and `golden_ok` along with runtime, paths, and status.

Golden tests are stricter checks on specific questions to ensure the planner summary is stable. The required cases are:

- `q06`: must include `Intent: funnel` and `Metrics: sessions, orders, conversion_rate`.
- `q07`: must include `Intent: summary`, `Metrics: count`, and `Dimensions: category`.
- `q20`: must include `Intent: comparison`, `Metrics: retention`, and `Dimensions: segment`.

If a case fails, open the report (for example `reports/evals/q06/report.md`) and the trace (`reports/evals/q06/trace.jsonl`) to see which step deviated.

## How to add a new dataset

1. **Match the expected schema.** The sample data uses `region`, `product`, `units`, and `price` columns (`data/sample.csv`). At minimum, include one categorical column (like `region` or `product`) and one numeric column (like `units` or `price`) so the SQL planner and chart tool can aggregate and visualize results.
2. **Place the CSV.** Save your file under `data/` (for example `data/your_dataset.csv`).
3. **Run the eval harness on it.**

   ```bash
   python -m analyst_agent eval --data data/your_dataset.csv --output-dir reports/evals --questions eval/questions.jsonl
   ```

4. **If the schema differs, update the rules.** Adjust `analyst_agent/planner.py` (intent/metric/dimension mappings) and, if needed, `analyst_agent/runner.py` SQL construction so column names in the dataset map to the expected metrics.
