"""Command-line entrypoint for RBL Content Engine V1 workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .weekly import run_weekly_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RBL Content Engine")
    sub = parser.add_subparsers(dest="command", required=True)

    weekly = sub.add_parser(
        "weekly",
        help="Build one offline 20-30s evidence-backed short-form content package",
    )
    weekly.add_argument("--brief", type=Path, required=True)
    weekly.add_argument("--claims", type=Path, required=True)
    weekly.add_argument("--theme", type=Path, required=True)
    weekly.add_argument("--output", type=Path, required=True)
    weekly.add_argument(
        "--workspace-root",
        type=Path,
        default=Path.cwd(),
        help="Workspace boundary for local evidence and inputs (default: cwd)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "weekly":
        result = run_weekly_pipeline(
            workspace_root=args.workspace_root,
            brief_path=args.brief,
            claims_path=args.claims,
            theme_path=args.theme,
            output_dir=args.output,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] != "BLOCKED" else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
