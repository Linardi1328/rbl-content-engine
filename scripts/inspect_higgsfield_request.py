"""Inspect an existing Higgsfield API request without submitting a new generation."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.local"


def safe_text(value: str) -> str:
    value = re.sub(
        r"(?i)(authorization\s*[:=]\s*key\s+)[^\s,;]+",
        r"\1[REDACTED]",
        value,
    )
    value = re.sub(
        r"(?i)(hf_(?:key|api_key|api_secret)\s*[:=]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        value,
    )
    value = re.sub(
        r"(?<![\w-])[A-Za-z0-9._-]{8,}:[A-Za-z0-9._-]{8,}(?![\w-])",
        "[REDACTED_CREDENTIAL]",
        value,
    )
    return value


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if key.lower() in {"authorization", "api_key", "api_secret", "hf_key"}
            else sanitize(item)
            for key, item in value.items()
        }
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect an existing Higgsfield request without resubmitting it."
    )
    parser.add_argument("request_id")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not ENV_FILE.is_file():
        print(".env.local is missing; no API request was made.")
        return 2

    load_dotenv(ENV_FILE, override=False)
    if "HF_KEY" not in os.environ:
        print("HF_KEY is not configured in .env.local; no API request was made.")
        return 2

    import higgsfield_client

    client = higgsfield_client.SyncClient()

    try:
        status = client.status(args.request_id)
        result = client.result(args.request_id)
    except higgsfield_client.HiggsfieldClientError as exc:
        print(
            "Higgsfield request inspection failed. "
            f"Provider message: {safe_text(str(exc))}"
        )
        return 1

    print(f"status_class={status.__class__.__name__}")
    print(json.dumps(sanitize(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
