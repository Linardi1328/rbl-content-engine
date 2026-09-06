"""Standalone CLI for deterministic Phase 1D-B media inspection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .media import inspect_media_reference


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rbl_content_engine.topview.media_cli",
        description="Inspect a local PNG/JPEG reference without Topview or network calls.",
    )
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--path", required=True)
    args = parser.parse_args(argv)

    try:
        result = inspect_media_reference(args.workspace_root, args.path)
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 2

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
