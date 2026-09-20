# Phase 4C — First RBL Launch Video Generation

## Purpose

Phase 4C uses the live-verified official Higgsfield Seedance 2.5 Text-to-Video API to create the first complete RBL launch-video review cut.

The operational boundary is:

```text
5 controlled Seedance shots
-> local MP4 downloads
-> deterministic local assembly
-> technical QC
-> PENDING_HUMAN_REVIEW
-> human decision
```

No social publication occurs in this phase.

## Verified model

`bytedance/seedance-2.5/text-to-video`

The owner environment successfully completed the official SDK smoke test on 2026-09-20 after funding the separate Higgsfield API balance.

Safe verification record:

`docs/production/LIVE_HIGGSFIELD_SEEDANCE25_2026-09-20.md`

## Launch configuration

Tracked plan:

`examples/production/rbl-launch-video-plan.json`

Current review-draft settings:

- 5 shots;
- 4 seconds each;
- 720p;
- 9:16;
- MP4;
- generated audio disabled;
- US$15 planned budget reservations;
- US$20 project ceiling.

The tracked cost values are conservative budget reservations, not claims about actual billing.

Actual charges must be checked from Higgsfield billing data. Do not silently replace estimated spend with actual spend.

## Generate shots

Credentials remain only in ignored `.env.local`.

```bash
git checkout phase-4c-launch-video-generation
uv sync --locked
uv run python scripts/generate_rbl_launch_video.py
```

The script:

- submits one request per incomplete shot;
- records the provider request ID immediately on enqueue;
- never automatically retries a paid mutation;
- stops on failed/canceled/moderated/provider-error outcomes;
- downloads successful outputs to ignored `.production/launch-video-outputs/`;
- validates each downloaded file as a non-trivial MP4;
- skips already completed local shots on rerun.

If a submission outcome is uncertain, inspect the recorded request ID/provider state before deciding whether another generation is justified.

## Assemble review cut

The local assembler requires `ffmpeg` and `ffprobe`.

```bash
uv run python scripts/assemble_rbl_launch_video.py
```

It:

- requires all five generation records and local MP4s;
- normalizes each clip to 720×1280 at 30 fps;
- strips generated audio;
- concatenates the five clips;
- writes:

`.production/launch-video-outputs/rbl-launch-review.mp4`

- verifies the final 720×1280 stream and approximately 20-second duration;
- updates ignored live state to `PENDING_HUMAN_REVIEW`.

If ffmpeg is unavailable, install it locally and rerun the assembler. Generated API shots are retained and must not be resubmitted just because local assembly is unavailable.

## Human review

The generated review cut must be shown to the human owner before any publication.

The review should assess:

- whether the hook is clear in the first seconds;
- whether the visual story actually represents evidence → verification → platform packaging → controlled generation;
- visual quality and continuity;
- unwanted invented text/logos;
- pacing;
- whether deterministic captions/voiceover should be added before publication;
- whether any shot needs a targeted retry.

A rejected shot does not justify automatic regeneration. Any retry is another explicit production decision and counts toward spend.

## Publication

Phase 4C has no publishing integration.

Even after a successful local assembly:

`publication_status = BLOCKED_PENDING_HUMAN_REVIEW`

The next publication step remains manual/external and requires explicit human approval.
