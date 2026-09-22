# V1 Weekly Short-Form Content Package

## Purpose

This is the minimum upstream workflow required for RBL Productions to create one
repeatable 20–30 second short-form content package without FacelessReels.

It is intentionally offline and deterministic.

```text
weekly brief/topic
+ local evidence-backed claims
+ human-authored channel theme
-> claim verification
-> canonical short-form script
-> storyboard / shot plan
-> PENDING_HUMAN
```

The channel theme is human creative direction. It may define recurring structure,
voice, visual style, generic connective lines, and the number/duration of story beats.
It is never evidence for a factual claim.

## Inputs

### Weekly brief

Required fields:

- `job_id`
- `project`
- `topic`
- `objective`
- `hook`
- `targets` using only `youtube`, `instagram`, and/or `tiktok`
- `approval_status` fixed to `PENDING_HUMAN`

### Claim manifest

Uses the existing evidence-reference contract:

- stable claim ID;
- factual claim text;
- local evidence path;
- 1-based inclusive line range;
- verbatim quote.

Every claim must be supported before script/storyboard generation proceeds.

### Channel theme

The theme is the reusable creative structure Esther can define for the channel.

Each beat has:

- stable `id`;
- `duration_seconds`;
- one source:
  - `brief_hook`
  - `next_claim`
  - `theme_text`
- `visual_direction`.

The total planned duration must be 20–30 seconds.

`theme_text` is human-authored creative language. It must not introduce factual
claims that are absent from the evidence set.

## Outputs

A successful run writes:

```text
content-package.json
script.md
storyboard.json
verifier-report.md
```

Successful state:

```text
status: READY_FOR_HUMAN_REVIEW
approval_status: PENDING_HUMAN
```

An unsupported claim produces a blocked content package and verifier report, but no
script or storyboard.

## Run the checked-in synthetic example

The checked-in channel theme is only a public-safe example. It is **not** Esther's
final RBL channel creative direction.

```bash
rm -rf examples/weekly/output

PYTHONPATH=src python -m rbl_content_engine weekly \
  --brief examples/weekly/sample-brief.json \
  --claims examples/weekly/sample-claims.json \
  --theme examples/weekly/sample-channel-theme.json \
  --output examples/weekly/output
```

The command performs no network calls, model calls, media generation, scheduling,
or publication.

## V1 boundary

This task does not implement:

- automated web research;
- an LLM script writer;
- platform-specific script variants;
- YouTube long-form content;
- viewer/comment optimization;
- analytics ingestion;
- media generation;
- publishing.

The next V1 production task is to make the already-live-verified Higgsfield
generation/assembly path consume a weekly job/storyboard without reusing the
launch-video-specific runtime state.
