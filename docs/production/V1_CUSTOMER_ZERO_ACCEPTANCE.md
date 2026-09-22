# V1 Customer Zero Acceptance

## Purpose

This is the final P0 gate before RBL Content Engine can move from internal alpha to
release-candidate preparation.

A Customer Zero PASS must come from **one real RBL Productions content item**. The
checked-in synthetic examples are useful for regression tests, but they cannot satisfy
this gate.

The accepted flow is:

```text
real brief/topic + evidence + Esther-approved channel theme
-> verified weekly content package
-> storyboard
-> job-scoped Seedance media plan
-> Higgsfield generation
-> local assembly + technical QC
-> PENDING_HUMAN_REVIEW
-> exact-asset Phase 5 human approval
-> schedule/publish through at least one ready live platform
-> COMPLETE publication receipt
-> offline acceptance evaluator
-> PASS
```

The acceptance evaluator itself performs zero network calls and zero paid mutations.
It only verifies artifacts produced by the real run.

## Acceptance rule

The run passes only when all of the following are true:

1. The human operator explicitly confirms the artifacts belong to a real RBL content
   item rather than a synthetic fixture.
2. The weekly content package is `READY_FOR_HUMAN_REVIEW`, verification is `PASS`,
   approval remains `PENDING_HUMAN`, and planned duration is 20–30 seconds.
3. The storyboard preserves the exact job ID, shot IDs, durations, and claim lineage
   from the weekly package.
4. The media plan uses the same `job_id`, passes the V1 Seedance contract, and keeps
   the storyboard shot IDs/durations unchanged.
5. Every planned generated shot has a `COMPLETED` runtime record.
6. The assembled review cut exists, is 720×1280, has `technical_qc: PASS`, matches
   the planned duration tolerance, and the media job stops at
   `PENDING_HUMAN_REVIEW`.
7. The Phase 5 post manifest matches the same job ID and its exact enabled platform
   assets still match the human-approved SHA-256 fingerprints/public URLs.
8. Every platform enabled for the acceptance post completes as `PUBLISHED` or
   `NATIVE_SCHEDULED` with no recorded error.
9. At least one enabled platform reaches an actual `PUBLISHED` state. A post that is
   only queued or native-scheduled is not enough.

## First acceptance platform

Use only providers that are truly ready for the real acceptance item. Do not enable a
platform merely to make the test look comprehensive.

For the first Customer Zero item, Instagram is the preferred live publication target
because the RBL Instagram Phase 5 path has already completed a live scheduler
publication smoke test. TikTok and YouTube may remain disabled in this first acceptance
manifest until their separate production/live-validation gates are ready.

A PASS therefore proves the complete RBL-owned weekly workflow end to end. It does
not falsely claim that every optional provider integration is already production-ready.

## Local artifact layout

Use a unique real job ID, for example:

`RBL-CZ-001`

Keep real acceptance inputs and operator files under ignored local state:

```text
.production/customer-zero/RBL-CZ-001/
  brief.json
  claims.json
  channel-theme.json
  weekly-output/
    content-package.json
    script.md
    storyboard.json
    verifier-report.md
  media-plan.json
  post-manifest.json
  queue.json
```

Higgsfield runtime remains in the existing job-scoped location:

```text
.production/jobs/RBL-CZ-001/
  higgsfield-state.json
  generation/
  review.mp4
```

The Phase 5 receipt remains:

```text
.production/publication-receipts/RBL-CZ-001.json
```

## Run order

### 1. Build the real weekly package

```bash
PYTHONPATH=src uv run --no-sync python -m rbl_content_engine weekly \
  --brief .production/customer-zero/RBL-CZ-001/brief.json \
  --claims .production/customer-zero/RBL-CZ-001/claims.json \
  --theme .production/customer-zero/RBL-CZ-001/channel-theme.json \
  --output .production/customer-zero/RBL-CZ-001/weekly-output
```

Do not proceed if verification is blocked.

### 2. Create the media plan

Create `.production/customer-zero/RBL-CZ-001/media-plan.json` from the approved
storyboard. It must keep the same `job_id`, shot IDs, and 4–8 second durations.

Prompt wording may add production description, camera language, lighting, and
non-factual style direction. It must not add unsupported story facts.

### 3. Generate the shots

This step is billable.

```bash
uv run python scripts/generate_rbl_launch_video.py \
  --plan .production/customer-zero/RBL-CZ-001/media-plan.json
```

Do not blindly rerun terminal failures. The existing explicit `--retry-shot` safety
rule remains in force.

### 4. Assemble and review

```bash
uv run python scripts/assemble_rbl_launch_video.py \
  --plan .production/customer-zero/RBL-CZ-001/media-plan.json
```

The result must stop at `PENDING_HUMAN_REVIEW`.

Review the actual MP4 before preparing publication assets. Rejected media is not
accepted merely because technical QC passed.

### 5. Prepare the Phase 5 manifest

For the first acceptance item, enable only live-ready targets. Copy/export the exact
approved final media into the relevant platform path(s), configure required metadata,
and stage any immutable HTTPS asset URL required by the provider.

Do not hand-write approval hashes.

### 6. Approve the exact current asset bytes

```bash
PYTHONPATH=src uv run --no-sync python -m rbl_content_engine.publishing approve \
  .production/customer-zero/RBL-CZ-001/post-manifest.json \
  --human-confirmed
```

### 7. Preflight, schedule, and publish

```bash
PYTHONPATH=src uv run --no-sync python -m rbl_content_engine.publishing preflight \
  .production/customer-zero/RBL-CZ-001/post-manifest.json

PYTHONPATH=src uv run --no-sync python -m rbl_content_engine.publishing schedule \
  .production/customer-zero/RBL-CZ-001/post-manifest.json \
  --queue .production/customer-zero/RBL-CZ-001/queue.json

PYTHONPATH=src uv run --no-sync python -m rbl_content_engine.publishing tick \
  --queue .production/customer-zero/RBL-CZ-001/queue.json
```

If a provider returns an asynchronous state, keep using `tick` for supported
reconciliation. Do not reschedule the same post after a successful/uncertain mutation.

### 8. Evaluate the recorded run

```bash
PYTHONPATH=src uv run --no-sync python -m rbl_content_engine.acceptance \
  --content-package .production/customer-zero/RBL-CZ-001/weekly-output/content-package.json \
  --storyboard .production/customer-zero/RBL-CZ-001/weekly-output/storyboard.json \
  --media-plan .production/customer-zero/RBL-CZ-001/media-plan.json \
  --generation-state .production/jobs/RBL-CZ-001/higgsfield-state.json \
  --post-manifest .production/customer-zero/RBL-CZ-001/post-manifest.json \
  --publication-receipt .production/publication-receipts/RBL-CZ-001.json \
  --human-confirmed-real-content
```

Required result:

```text
status: PASS
failed_checks: []
network_calls: 0
paid_mutations: 0
```

The last two fields describe the evaluator only. The preceding generation/publication
steps are real external actions and may incur provider/API costs.

## Current human-input blocker

The repository intentionally does not contain Esther's final RBL channel
theme/storyline or a selected first real Customer Zero topic. Those must be supplied by
the humans responsible for the channel. The acceptance run must not substitute the
synthetic sample theme for that decision.

Once the real theme and first topic/evidence are available, no additional V1 feature
work should be introduced before attempting this run. Any defect discovered by the
real run that blocks completion is promoted to P0; otherwise a PASS moves the project
to release-candidate preparation.
