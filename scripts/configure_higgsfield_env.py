"""Securely create the ignored .env.local file for Higgsfield API access.

Run this locally. The credential is entered with hidden terminal input and is never
printed. This script does not send it anywhere.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env.local"


def main() -> int:
    credential = getpass.getpass(
        "Enter Higgsfield HF_KEY locally (key-id:key-secret): "
    ).strip()

    if not credential or ":" not in credential:
        print("Invalid HF_KEY format; expected key-id:key-secret.")
        return 1

    ENV_FILE.write_text(f"HF_KEY={credential}\n", encoding="utf-8")
    os.chmod(ENV_FILE, 0o600)

    print(".env.local configured locally with restrictive permissions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
