"""Command-line interface for analyst_agent."""

import argparse
import sys

from analyst_agent.eval_harness import run_eval
from analyst_agent.runner import run_question
from pathlib import Path

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyst agent MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run an analysis question")
    run_parser.add_argument("--question", required=True, help="Question to analyze")
    run_parser.add_argument("--data", required=True, help="Path to CSV data")
    run_parser.add_argument(
        "--report-path",
        default="reports/latest.md",
        help="Output path for the report markdown",
    )
    run_parser.add_argument(
        "--trace-path",
        default="reports/trace.jsonl",
        help="Output path for JSONL trace logs",
    )

    eval_parser = subparsers.add_parser("eval", help="Run evaluation harness")
    eval_parser.add_argument("--data", required=True, help="Path to CSV data")
    eval_parser.add_argument(
        "--output-dir",
        default="reports/evals",
        help="Directory for eval outputs",
    )
    eval_parser.add_argument(
    "--questions",
    default=str(Path("eval") / "questions.jsonl"),
    help="Path to JSONL questions file",
)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        run_question(
            question=args.question,
            data_path=args.data,
            report_path=args.report_path,
            trace_path=args.trace_path,
        )
        return

    if args.command == "eval":
        success = run_eval(
            data_path=args.data,
            output_dir=args.output_dir,
        questions_path=args.questions,
    )
    sys.exit(0 if success else 1)



if __name__ == "__main__":
    main()
