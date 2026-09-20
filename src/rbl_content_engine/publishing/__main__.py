"""CLI for Phase 5 social publishing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import (
    DEFAULT_QUEUE,
    ScheduleQueue,
    load_post_manifest,
    publish_due_jobs,
    run_scheduler,
)


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

    schedule = sub.add_parser(
        "schedule",
        help="Add a validated post manifest to the local scheduler queue",
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

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
