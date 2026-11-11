# RIC-139 — Offline social finishing

This is a new minimum equivalent implementation of the V5 finishing behavior.
The uploaded V5 archive contains an MP4, QC report, machine-estimated timing JSON,
and README, **no editable Python source**. No original scripts were recovered or
ported. The archive's timings explicitly say `NOT_HUMAN_VERIFIED` and must not be
reused as production-approved cues. The archive's old narration is not the new
approved ONE MORE SHOT Kokoro WAV.

## Inputs and scope

Use an existing weekly job's silent `review.mp4` after assembly has reached
`PENDING_HUMAN_REVIEW`. Keep its `higgsfield-state.json`, verified weekly content
package, storyboard, and media plan. Finishing reads them without changing any bytes.
The plan, shot IDs/durations, script text, claim IDs, and evidence references must
agree. The transcript is taken from the verified weekly script; it is not generated.

Supply these new owner-controlled local inputs:

- Approved ONE MORE SHOT Kokoro narration WAV, at its original speed/pitch.
- Word timings derived from that **exact WAV**, corrected by a human listening to
  it, including punctuation and every script word in order. Record the WAV SHA-256,
  derivation method, reviewer, timezone-aware review timestamp, and verification of
  each cue. The program checks these attestations and hashes; it does not perform
  forced alignment or independently establish that a human listened.
- Approved/licensed music covering the full video, plus optional approved/licensed
  SFX with explicit offsets. Each audio file has a hash, license/source description,
  reviewer, review timestamp and gain from -40 to 0 dB. Rights are human attestations,
  not automatically verified licensing decisions.

Narration must fit the cut; music must cover it; SFX must fit without truncation.
No implicit looping, narration time stretching, automatic realignment, or machine
approval. The runner rejects missing, extra, reordered, overlapping, unverified,
out-of-range, non-finite, or sub-centisecond cues. Pauses between words are allowed.
Caption override syntax/control characters and oversized words are rejected.

## Run

Copy the intentionally blocked templates into ignored local state and complete them:

- `examples/production/social-finishing.example.json`
- `examples/production/social-word-timings.example.json`

Paths resolve from the repository root, including paths in manifests stored elsewhere;
absolute paths within the repository are also supported. Keep live inputs/media under
`.production/jobs/<job_id>/` or `.production/customer-zero/<job_id>/`.

On Mac, use FFmpeg with libass. The standard Homebrew FFmpeg may lack it; install
`ffmpeg-full` if needed and pass its executable explicitly. No global relink is needed.

```bash
PYTHONPATH=src uv run --no-sync python -m rbl_content_engine.production.finishing \
  .production/jobs/JOB_ID/finishing.json \
  --ffmpeg /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg \
  --ffprobe /opt/homebrew/opt/ffmpeg-full/bin/ffprobe
```

Two words remain visible together in the mobile safe area; yellow highlighting
advances sequentially to the active word, one ASS event per cue. A final odd word
retains the preceding word as context. Caption sizing is bounded by word length.
Libass burns captions into the existing picture. Narration drives sidechain ducking
of the music/SFX bed (10ms attack, 250ms release, 8:1 ratio), followed by a peak limiter.
These are conservative fixed defaults; listen to the full mix before final approval.

## Outputs and QC

The same job directory receives four separate, immutable outputs:

```text
final-social-review.mp4
final-social-review.sha256
social-captions.ass
social-finishing-qc.json
```

QC checks 720×1280 H.264 video, stereo AAC at 48kHz, video/audio durations against the
silent cut, full-file decode, audible input/output levels, caption event structure,
and unchanged hashes of every input. The JSON retains hashes/paths for the silent
cut, Higgsfield state, content package, storyboard, plan, WAV, timings, music, SFX and
finishing manifest, plus the final SHA-256 and FFmpeg version. Technical QC cannot
judge speech sync, visual taste, licensing, or perceived loudness; those remain human
review items.

Rendering occurs in an isolated temporary directory. Only a successfully validated
cut is installed, using atomic no-clobber links. Existing files or symlinks at any
output name block the run, including an already approved final asset. There is no
force/overwrite switch. An exclusive job lock prevents concurrent finishing runs.
An interrupted process may leave a lock; investigate before manually removing it.
A corrected revision needs a separately identified job; do not delete an approved
asset to reuse its filename. A crash during installation may leave partial output
files, which block reruns and require operator investigation.

The report always stops at `PENDING_HUMAN_REVIEW` and
`BLOCKED_PENDING_HUMAN_REVIEW`. The original silent assembler and historical launch
behavior remain unchanged. No provider calls, paid generation, frontend, scheduling,
approval mutation, or publication occur here.

## Exact approval and Customer Zero

Listen/watch the actual finished MP4. After explicit human review, prepare Phase 5
exports as exact copies of this file and use the existing `publishing approve` command
to bind approval to the current bytes and public URL. Never reuse silent-cut approval
or hand-write approval hashes. Finishing QC is not publication approval.

The Customer Zero evaluator automatically enforces a finishing report beside the
job's generation state when present. It also accepts an explicit
`--finishing-report .production/jobs/JOB_ID/social-finishing-qc.json` argument. Use
that flag when moving records or invoking the evaluator with a state copy. The check
requires current input hashes, the same upstream package/storyboard/plan/state, the
finished file hash, and identical approved hashes for every enabled Phase 5 export.
Re-encoding or otherwise altering a platform export requires a future explicit
export-lineage contract; this minimum path accepts exact copies only.

Silent-only historical acceptance remains compatible. Synthetic tests exercise the
machinery but do not establish a real Customer Zero PASS. The new approved WAV,
human-corrected cues and licensed assets remain operator prerequisites for the real
ONE MORE SHOT run. Do not mark them approved simply to run the example.

## Verification

```bash
make check
make lint
make typecheck
RBL_FFMPEG=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg \
RBL_FFPROBE=/opt/homebrew/opt/ffmpeg-full/bin/ffprobe \
make test PYTHON='.venv/bin/python'
make build
```

Media integration tests use synthetic tones and video only. They render/decode a
20-second cut with libass, check actual music attenuation under narration, preserve
silent/state bytes, reject clobbers/invalid inputs, and exercise finished-file
Customer Zero lineage. They skip on environments without libass; the explicit Mac
run above is required in addition to repository CI.
