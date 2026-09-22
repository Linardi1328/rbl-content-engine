"""CLI for Phase 5 social publishing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import (
    DEFAULT_QUEUE,
    ScheduleQueue,
    TikTokPublisher,
    approve_post_manifest,
    load_post_manifest,
    publish_due_jobs,
    run_scheduler,
)
from .tiktok_auth import DEFAULT_REDIRECT_URI, run_desktop_oauth


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RBL direct social publishing scheduler"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser(
        "preflight",
        help="Validate a post manifest without network calls",
    )
    preflight.add_argument("manifest", type=Path)

    approve = sub.add_parser(
        "approve",
        help="Explicitly approve the exact current platform assets for publication",
    )
    approve.add_argument("manifest", type=Path)
    approve.add_argument(
        "--human-confirmed",
        action="store_true",
        help="Required explicit confirmation that the final media was reviewed",
    )

    schedule = sub.add_parser(
        "schedule",
        help="Add a validated and human-approved post manifest to the local scheduler queue",
    )
    schedule.add_argument("manifest", type=Path)
    schedule.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)

    tick = sub.add_parser(
        "tick",
        help="Publish/reconcile due jobs once",
    )
    tick.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)

    daemon = sub.add_parser(
        "daemon",
        help="Continuously publish/reconcile posts by scheduled datetime",
    )
    daemon.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    daemon.add_argument("--poll-seconds", type=float, default=30.0)

    status = sub.add_parser("status", help="Show local scheduler state")
    status.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)

    retry = sub.add_parser(
        "retry-platform",
        help=(
            "Explicitly reset one FAILED/BLOCKED platform to SCHEDULED. "
            "RECONCILE_REQUIRED is intentionally not reset by this command."
        ),
    )
    retry.add_argument("post_id")
    retry.add_argument("platform")
    retry.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)

    tiktok_auth = sub.add_parser(
        "tiktok-auth",
        help="Authorize TikTok Desktop Login Kit with PKCE and store refresh-token state",
    )
    tiktok_auth.add_argument(
        "--redirect-uri",
        default=DEFAULT_REDIRECT_URI,
        help=f"Registered TikTok Desktop redirect URI (default: {DEFAULT_REDIRECT_URI})",
    )
    tiktok_auth.add_argument(
        "--scopes",
        default="user.info.basic,video.publish",
        help="Comma-separated TikTok scopes",
    )
    tiktok_auth.add_argument(
        "--state-path",
        type=Path,
        default=None,
        help="Optional token-state path override",
    )
    tiktok_auth.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the authorization URL without opening the system browser",
    )
    tiktok_auth.add_argument(
        "--timeout-seconds",
        type=float,
        default=300.0,
        help="Local callback listener timeout",
    )

    sub.add_parser(
        "tiktok-creator-info",
        help=(
            "Refresh TikTok auth if needed and query the connected creator's "
            "current Direct Post capabilities"
        ),
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "preflight":
        manifest = load_post_manifest(args.manifest)
        enabled = [
            name
            for name, config in manifest["platforms"].items()
            if config.get("enabled", True)
        ]
        print(
            json.dumps(
                {
                    "status": "READY_LOCAL_PREFLIGHT",
                    "post_id": manifest["post_id"],
                    "scheduled_at": manifest["scheduled_at"],
                    "platforms": enabled,
                    "network_calls": 0,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "approve":
        approved = approve_post_manifest(
            args.manifest,
            human_confirmed=args.human_confirmed,
        )
        print(
            json.dumps(
                {
                    "status": "APPROVED_FOR_PUBLICATION",
                    "post_id": approved["post_id"],
                    "confirmed_at": approved["approval"]["confirmed_at"],
                    "platforms": sorted(approved["approval"]["asset_sha256"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "schedule":
        queue = ScheduleQueue(args.queue)
        job = queue.add_manifest(args.manifest)
        print(
            json.dumps(
                {
                    "status": "SCHEDULED",
                    "post_id": job.job_id,
                    "scheduled_at": job.scheduled_at,
                    "queue": str(args.queue),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "tick":
        queue = ScheduleQueue(args.queue)
        events = publish_due_jobs(queue)
        print(
            json.dumps(
                {
                    "events": events,
                    "queue": str(args.queue),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "daemon":
        run_scheduler(args.queue, poll_seconds=args.poll_seconds)
        return 0

    if args.command == "status":
        queue = ScheduleQueue(args.queue)
        print(
            json.dumps(
                {
                    "queue": str(args.queue),
                    "jobs": [job.to_dict() for job in queue.jobs],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "retry-platform":
        queue = ScheduleQueue(args.queue)
        matched = False
        for job in queue.jobs:
            if job.job_id != args.post_id:
                continue
            state = job.platforms.get(args.platform)
            if state is None:
                raise SystemExit(
                    f"{args.post_id} has no enabled platform {args.platform}"
                )
            if state.get("status") == "RECONCILE_REQUIRED":
                raise SystemExit(
                    "RECONCILE_REQUIRED cannot be blindly retried because the "
                    "previous provider mutation may have succeeded. Reconcile "
                    "the provider state first."
                )
            if state.get("status") not in {"FAILED", "BLOCKED"}:
                raise SystemExit(
                    "retry-platform only accepts FAILED or BLOCKED platform state"
                )
            job.platforms[args.platform] = {"status": "SCHEDULED"}
            job.status = "SCHEDULED"
            matched = True
            break
        if not matched:
            raise SystemExit(f"post not found: {args.post_id}")
        queue.save()
        print(f"{args.post_id}:{args.platform}:SCHEDULED")
        return 0

    if args.command == "tiktok-auth":
        scopes = tuple(scope.strip() for scope in args.scopes.split(",") if scope.strip())
        result = run_desktop_oauth(
            redirect_uri=args.redirect_uri,
            scopes=scopes,
            state_path=args.state_path,
            open_browser=not args.no_browser,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "tiktok-creator-info":
        creator = TikTokPublisher.from_env().creator_info()
        safe_fields = (
            "creator_username",
            "creator_nickname",
            "privacy_level_options",
            "comment_disabled",
            "duet_disabled",
            "stitch_disabled",
            "max_video_post_duration_sec",
        )
        print(
            json.dumps(
                {key: creator.get(key) for key in safe_fields},
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
