"""Billable Seedance 2.5 text-to-video smoke test using Higgsfield's official SDK.

Run from the repository root after creating a local, ignored .env.local file:

    HF_KEY=key-id:key-secret

This example never reads or prints the credential value itself. python-dotenv loads the
file into the process environment and the official Higgsfield SDK consumes HF_KEY.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv


MODEL = "bytedance/seedance-2.5/text-to-video"
PROMPT = "A cinematic scene at sunset"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env.local"


def _extract_video_url(result: Mapping[str, Any]) -> str:
    video = result.get("video")

    if isinstance(video, str) and video.startswith(("https://", "http://")):
        return video

    if isinstance(video, Mapping):
        url = video.get("url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            return url

    raise RuntimeError("completed request did not return a recognizable video URL")


def main() -> int:
    # Require the explicit ignored local file rather than silently using ambient
    # credentials from another tool/runtime.
    if not ENV_FILE.is_file():
        print(
            ".env.local is missing. Configure HF_KEY locally with "
            "scripts/configure_higgsfield_env.py; do not paste it into chat."
        )
        return 2

    # Keep credentials local and server-side. Never read/print the value in
    # application code; python-dotenv loads it and the official SDK consumes it.
    load_dotenv(ENV_FILE, override=False)

    if "HF_KEY" not in os.environ:
        print(
            "HF_KEY is not configured. Enter it locally in .env.local as "
            "HF_KEY=key-id:key-secret; do not paste it into chat."
        )
        return 2

    import higgsfield_client

    terminal_failure: str | None = None

    def on_queue_update(status: Any) -> None:
        nonlocal terminal_failure
        if isinstance(status, higgsfield_client.Failed):
            terminal_failure = "failed"
        elif isinstance(status, higgsfield_client.Cancelled):
            terminal_failure = "canceled"
        elif isinstance(status, higgsfield_client.NSFW):
            terminal_failure = "moderated"

    try:
        result = higgsfield_client.subscribe(
            MODEL,
            arguments={
                "prompt": PROMPT,
                "duration": 5,
                "resolution": "720p",
                "aspect_ratio": "16:9",
            },
            on_queue_update=on_queue_update,
        )
    except higgsfield_client.CredentialsMissedError:
        print(
            "Higgsfield credentials are unavailable. Enter HF_KEY locally in "
            ".env.local and rerun; do not paste the secret into chat."
        )
        return 2
    except higgsfield_client.HiggsfieldClientError:
        print(
            "Higgsfield API request failed. Check the local credential, prepaid "
            "API balance, and request access; no successful generation is claimed."
        )
        return 1

    if terminal_failure is not None:
        print(
            f"Higgsfield request ended as {terminal_failure}; "
            "no successful generation is claimed."
        )
        return 1

    if not isinstance(result, Mapping):
        print("Higgsfield returned an unexpected result; no success is claimed.")
        return 1

    try:
        video_url = _extract_video_url(result)
    except RuntimeError:
        print("Higgsfield completed without a usable video URL; no success is claimed.")
        return 1

    print(video_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
