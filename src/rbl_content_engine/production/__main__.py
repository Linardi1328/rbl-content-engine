"""Command-line entry point for deterministic Stage 3 evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from .io import load_stage3_evaluation, render_stage3_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rbl_content_engine.production",
        description="Evaluate Stage 3 production/readiness fixtures offline.",
    )
    parser.add_argument("input", help="Path to a Stage 3 JSON fixture")
    parser.add_argument(
        "--output",
        help="Optional path for the deterministic JSON report",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    evaluation = load_stage3_evaluation(args.input)
    report = render_stage3_report(evaluation)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
