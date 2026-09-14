from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .analytics import load_analytics
from .models import ManifestError, load_manifest
from .reporting import write_outputs


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Offline RBL revenue and audience intelligence."
    )
    p.add_argument("manifest", help="Opportunity manifest JSON path")
    p.add_argument(
        "--analytics",
        help="Optional manually exported first-party analytics CSV",
    )
    p.add_argument("--output", required=True, help="Output directory")
    p.add_argument(
        "--workspace",
        default=".",
        help="Workspace root used to validate research snapshot lineage",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest, workspace=Path(args.workspace))
        analytics = load_analytics(args.analytics) if args.analytics else None
        written = write_outputs(args.output, manifest, analytics)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
