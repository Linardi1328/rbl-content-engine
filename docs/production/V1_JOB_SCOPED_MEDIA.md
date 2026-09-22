# V1 Job-Scoped Higgsfield Media Production

## Purpose

The live-verified Seedance 2.5 generation and local assembly path must be reusable for
weekly RBL content without one job overwriting another job's request IDs, clips, or
review cut.

The V1 runtime layout is:

```text
.production/jobs/<job_id>/
  higgsfield-state.json
  generation/
    S01.mp4
    S02.mp4
    ...
  review.mp4
```

The whole directory is gitignored.

## Plan contract

Weekly plans use `job_id` and keep the existing production controls:

- model: `bytedance/seedance-2.5/text-to-video`;
- 9:16;
- 720p review drafts;
- MP4;
- generated audio disabled;
- 4–8 seconds per generated shot;
- target duration equals the sum of shot durations;
- V1 weekly total duration: 20–30 seconds;
- explicit estimated USD reservation per shot;
- project budget at or below US$20;
- publication policy fixed to
  `PENDING_HUMAN_REVIEW_BEFORE_ANY_PUBLICATION`.

Synthetic example:

`examples/production/weekly-video-plan.example.json`

## Generate

Credentials remain in ignored `.env.local`.

```bash
uv run python scripts/generate_rbl_launch_video.py \
  --plan examples/production/weekly-video-plan.example.json
```

Despite the historical script filename, supplying a plan with `job_id` uses the
job-scoped V1 runtime path.

The generator preserves the existing paid-mutation safety behavior:

- one submission per incomplete shot;
- request ID recorded on enqueue;
- completed local shots are resumed/skipped;
- terminal failures require explicit `--retry-shot S0X`;
- no automatic paid retry after an uncertain or failed mutation.

## Assemble

After all planned shots are generated:

```bash
uv run python scripts/assemble_rbl_launch_video.py \
  --plan examples/production/weekly-video-plan.example.json
```

The assembler reads the same job-scoped state, concatenates the generated clips,
checks the 720×1280 stream and expected total duration, then writes:

```text
.production/jobs/<job_id>/review.mp4
```

Successful assembly stops at:

```text
status: PENDING_HUMAN_REVIEW
publication_status: BLOCKED_PENDING_HUMAN_REVIEW
```

It does not publish.

## Historical launch compatibility

Running either script with no `--plan` continues to use the historical launch plan
and historical runtime paths:

```text
.production/rbl-launch-video.json
.production/launch-video-outputs/
```

This preserves the already-live-verified launch evidence and avoids migrating old
runtime state during the V1 completion sprint.

## V1 boundary

This task does not:

- submit any validation/test generation job;
- change the Higgsfield model;
- change OAuth/credentials;
- automate prompt writing from the storyboard;
- change Phase 5 publishing;
- add a database or worker service.

The next release gate after this task is one real Customer Zero content item through
the complete weekly path, with any newly discovered failure promoted to P0.
