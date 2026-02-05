# My-first-agent-program

## MVP Analyst Agent

This repository contains a minimal analyst agent that:
- Loads a CSV into DuckDB.
- Builds a simple analysis plan.
- Runs a SQL query and generates a chart.
- Writes a Markdown report to `reports/latest.md`.
- Emits structured JSONL tracing.
- Includes a lightweight eval harness.

### Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

### Run the MVP

```bash
python -m analyst_agent run --question "Which region has the highest average units?" --data data/sample.csv
```

This writes:
- `reports/latest.md`
- `reports/trace.jsonl`
- `charts/latest.png`

### Run the eval harness

```bash
python -m analyst_agent eval --data data/sample.csv
```

Reports and traces will be written under `reports/evals`.
