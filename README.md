# RBL Content Engine

Evidence-driven manual content pipeline for RBL Productions.

## Repository scope and current milestone

Phase 0 remains the evidence-to-content foundation. Phase 2A/2B add the accepted offline revenue/audience learning loop. The active production milestone is **Phase 5 — Direct Social Publishing**, adding an RBL-owned scheduler and direct Instagram/TikTok/YouTube publishing adapters after the approved production workflow. Phase 0–4 remain historically scoped to their original human-review/publication boundaries.

Phase 0 turns verified project/GitHub evidence into platform-native content drafts while keeping factual evidence and market strategy separate:

```text
project/GitHub evidence
  -> extracted claims
  -> evidence verification / local ProofLab contract

human direction brief
+ dated platform research
  -> platform strategy

verified claims + strategy
  -> YouTube / Instagram / TikTok treatments
  -> verifier report
  -> storyboard(s)
  -> HUMAN APPROVAL
```

The repository deliberately stops at human approval. It does **not** publish content, message customers, spend money, call paid APIs, perform live trend research, or automate video creation.

PR #6 introduced a small local ProofLab-style contract in `src/rbl_content_engine/prooflab.py`. It provides `VerifiedClaim` and the fail-closed `require_verified_claims()` boundary for future generation contracts. This is local, dependency-free verification code; it does **not** authorize an external ProofLab service, network integration, or paid ProofLab action.

## Core idea

The engine separates two questions:

- **What are we allowed to say?** Project evidence and claim verification decide this.
- **How should we tell the story on this platform?** A human direction brief plus a dated platform-research snapshot decide this.

Market research may influence the hook, pacing, format, visual treatment, and audience strategy, but it can never be used to invent or validate a project fact.

The local ProofLab boundary fails closed before factual claims may enter future AI-generation or Topview-production paths.

## Non-negotiable rules

- Every factual project claim must trace to project evidence.
- Unsupported claims must be flagged and must block a publish-ready result.
- Project evidence references must survive the full pipeline.
- Future factual generation inputs must pass the local `require_verified_claims()` boundary.
- Platform strategy must retain snapshot/date/source lineage.
- Never promise or imply guaranteed views, virality, reach, or algorithmic preference.
- Human approval is always required before publication.
- No secrets or credentials belong in the repo.
- Prefer Python standard library and deterministic logic over frameworks or agents.
- No social posting or customer messaging actions.
- No live platform/API research in the Phase 0 runner.
- No video automation or paid model calls in Phase 0.
- No external/network ProofLab integration in Phase 0.

## Repository shape

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml
├── Makefile
├── docs/
│   ├── phase-0-spec.md
│   ├── platform-intelligence.md
│   ├── codex-phase-0-prompt.md
│   └── topview/
│       ├── WORKFLOW.md
│       ├── TOOL_MAP.md
│       ├── DISCOVERY.md             # Phase 1B live MCP discovery procedure
│       └── PHASE_1D_PILOT.md        # controlled preflight/reference pilot
├── schemas/
│   ├── topview-production.schema.json
│   ├── topview-state.schema.json
│   ├── topview-capabilities.schema.json
│   └── topview-references.schema.json
├── .production/
│   ├── topview-state.example.json
│   ├── topview-capabilities.example.json
│   └── topview-references.example.json
├── research/
│   └── platforms/
│       └── 2026-08-21/
│           └── platforms.json
├── examples/
│   ├── taskpebble/
│   └── topview/
│       └── reference-pilot/         # synthetic/public-safe Phase 1D fixture
├── src/
│   └── rbl_content_engine/
│       ├── __init__.py
│       ├── prooflab.py              # local fail-closed factual contract
│       ├── ai_generation.py         # provider-neutral generation contract
│       └── topview/
│           ├── validator.py         # Phase 1C semantic contract validation
│           ├── preflight.py         # Phase 1C fail-closed future-production evaluator
│           ├── pilot.py             # Phase 1D non-chargeable technical preflight
│           ├── references.py        # Phase 1D reference fingerprints/approval/locks
│           └── __main__.py          # local CLI; no media generation
└── tests/
```

Codex should implement Phase 0 from `docs/codex-phase-0-prompt.md`, while treating `AGENTS.md` and `docs/phase-0-spec.md` as authoritative constraints. Topview work must also follow `docs/topview/WORKFLOW.md`, `docs/topview/TOOL_MAP.md`, `docs/topview/DISCOVERY.md`, and the applicable pilot document.

## Platform treatments in the demo

The TaskPebble direction brief requests four deterministic treatments from the same verified claim set:

- YouTube long-form — concept/title/hook/outline only;
- YouTube Shorts — short-form script + storyboard;
- Instagram Reels — short-form script + storyboard;
- TikTok — short-form script + storyboard.

The drafts should be meaningfully platform-native, not identical copy with different labels.

## Development

Target runtime: Python 3.11+.

```bash
make check
make test
```

The project intentionally starts dependency-free. Add a dependency only when the standard library cannot reasonably satisfy a concrete requirement, and document why.

## Intended Phase 0 run

```bash
PYTHONPATH=src python -m rbl_content_engine \
  examples/taskpebble/claims.json \
  --direction examples/taskpebble/direction.json \
  --platform-research research/platforms/2026-08-21/platforms.json \
  --output examples/taskpebble/output
```

The runner must operate fully offline.

## Phase 0 exit criteria

A single manual end-to-end run using synthetic/public-safe evidence must produce:

- an evidence/claim set;
- a platform strategy/content plan with source lineage;
- a YouTube long-form concept;
- platform-native YouTube Shorts, Instagram Reels, and TikTok drafts;
- a verifier result that keeps project verification separate from strategy verification;
- short-form storyboards;
- a pending human-approval state;

with no publication or other external side effects.

## Phase 1 Topview operator contract

Phase 1 adds the contract and local safety machinery for a future controlled visual-production subsystem without enabling paid generation.

The intended boundary is:

```text
project evidence
-> VerifiedClaim
-> require_verified_claims()
-> approved content/script/shot manifest
-> Topview Production Manifest
-> live Topview capability discovery
-> local validation / preflight
-> controlled reference preparation
-> Codex as RBL Topview Production Operator
-> future Topview rendering
-> QC
-> HUMAN APPROVAL
```

Topview is a renderer/production subsystem, not a factual verifier or creative authority.

### Phase 1B — live capability discovery

A Codex session with Topview actually installed must discover the live MCP/plugin surface and write:

```text
.production/topview-capabilities.json
```

The live file is gitignored. It uses stable RBL capability IDs so changing Topview tool names do not change the production methodology. `VERIFIED_LIVE` may only come from the active MCP session; public documentation remains `OFFICIAL_DOC` in `TOOL_MAP.md`.

The current ChatGPT environment cannot complete that live promotion because Topview is not connected here. See `docs/topview/DISCOVERY.md` for the exact Codex procedure.

### Phase 1C — local validator and preflight

The dependency-free validator checks the safety invariants that matter before future production:

- ProofLab verification boundary and scene factual lineage;
- budget ceilings and estimated per-video spend;
- reference IDs and continuity links;
- 4–8 second generated-clip default / long-clip justification;
- factual-lineage QC requirement;
- production state cannot advance or contain generated tasks before ready preflight;
- `VERIFIED_LIVE` capabilities require actual observed tool metadata.

Core commands:

```bash
PYTHONPATH=src python -m rbl_content_engine.topview validate-manifest path/to/manifest.json
PYTHONPATH=src python -m rbl_content_engine.topview validate-state .production/topview-state.json
PYTHONPATH=src python -m rbl_content_engine.topview validate-capabilities .production/topview-capabilities.json
PYTHONPATH=src python -m rbl_content_engine.topview preflight \
  --manifest path/to/manifest.json \
  --state .production/topview-state.json \
  --capabilities .production/topview-capabilities.json
```

These commands perform no MCP/network calls. Phase 1 preflight intentionally blocks chargeable generation even when synthetic/live capability checks otherwise pass; paid execution requires a later explicit human-authorized phase.

### Phase 1D — controlled preflight and reference pilot

Phase 1D introduces the first resumable production-control lifecycle while still stopping before generation:

```text
live discovery
-> technical preflight
-> explicit human preflight confirmation
-> stage 1–2 manifest references
-> fingerprint local source bytes with SHA-256
-> record only observed remote Topview asset IDs
-> explicit human reference approval
-> cryptographic reference lock
-> stop
```

Live mutable registry:

```text
.production/topview-references.json
```

This file is gitignored. A locked reference binds its RBL reference ID to the manifest type, source path, source fingerprint, observed remote asset ID, and human approval. If source bytes change later, the pilot blocks with reference drift rather than silently accepting the replacement.

Phase 1D CLI commands include:

```bash
PYTHONPATH=src python -m rbl_content_engine.topview phase1d-preflight ...
PYTHONPATH=src python -m rbl_content_engine.topview phase1d-confirm-preflight ... --human-confirmed
PYTHONPATH=src python -m rbl_content_engine.topview reference-init ...
PYTHONPATH=src python -m rbl_content_engine.topview reference-record-remote ...
PYTHONPATH=src python -m rbl_content_engine.topview reference-approve ... --human-confirmed
PYTHONPATH=src python -m rbl_content_engine.topview reference-lock ...
PYTHONPATH=src python -m rbl_content_engine.topview reference-pilot-status ...
```

The exact invocation and hard-stop policy are documented in `docs/topview/PHASE_1D_PILOT.md`.

Phase 1D does not call Topview itself from this Python package, does not submit any generation task, and requires actual project spend to remain US$0.

## Phase 3A — provider-neutral production contract

Phase 3A starts the production-development roadmap after accepted Phase 2 while preserving all earlier factual and human-approval boundaries.

The durable policy is:

```text
RBL evidence / strategy / SceneCards / references / QC
-> provider-neutral production need
-> capability + cost preflight
-> explicit human authorization
-> replaceable renderer
```

Prototype progression is:

```text
PROVE_PIPELINE
-> PROVE_REPEATABILITY
-> STABILIZE_PROVIDER
-> HUMAN PROVIDER / SUBSCRIPTION DECISION
```

The default stability gate requires at least five completed/published prototype videos, complete retry/QC/cost records, at least three first-party social observation records, and explicit human confirmation. Reaching the gate authorizes no spend by itself.

Free/trial capacity may be used later when legitimately owned by the human/workspace, but RBL must not depend on temporary grants or public/shared API credentials. Provider migrations must preserve SceneCards, ProofLab lineage, reference locks, continuity, QC, and approval gates.

Implementation authority: `docs/production/PHASE_3A_SPEC.md` and `src/rbl_content_engine/production/`.

Phase 3A contains no live provider adapter or generation submission path. A later explicitly authorized milestone may add controlled provider discovery and a single keyframe pilot.

## Stage 3B–3E — controlled production prototype

Stage 3 continues the provider-neutral architecture into a real production lifecycle:

```text
3B  provider discovery + controlled keyframe
-> 3C approved-keyframe video prototype
-> 3D repeatability + manual publication observations
-> 3E provider stabilization readiness
```

The production package now distinguishes provider/model discovery, cost estimation, and live execution eligibility. A model may appear in the catalog and expose a valid quote while still being blocked for the active account tier; such a model must fail closed in production preflight.

Stage 3D never publishes content. It accepts only human-confirmed `MANUAL_EXTERNAL` publication receipts plus matching first-party social observations. The five-video / three-observation threshold is a process-readiness gate, not a claim of creative or commercial success.

Stage 3E emits provider evidence and keeps provider selection as `HUMAN_DECISION_REQUIRED`. It does not subscribe to Higgsfield, activate a trial, create an API account, or migrate providers automatically.

Deterministic offline evaluation:

```bash
PYTHONPATH=src python -m rbl_content_engine.production \\
  examples/production/stage3-complete.json
```

Live provider/account state belongs under ignored `.production/` files. Safe dated findings from the 2026-09-20 implementation session are recorded in `docs/production/LIVE_FINDINGS_2026-09-20.md`.

## Phase 4A — official Higgsfield API launch video

Phase 4A adds Higgsfield's official pay-as-you-go API as a real RBL execution backend for the first complete launch-video prototype.

```text
tracked 9:16 launch plan
-> current live Higgsfield API application path
-> USD cost preflight
-> official higgsfield-client SDK
-> controlled shot generation
-> QC
-> assemble final cut
-> PENDING_HUMAN_REVIEW
-> explicit human approval
-> manual/external publication
```

The project now installs the official Python SDK and local environment loader through its existing `uv` lock:

```bash
uv sync --locked
```

The Seedance 2.5 smoke test uses the official application path:

`bytedance/seedance-2.5/text-to-video`

Credentials remain local in ignored `.env.local` as `HF_KEY=key-id:key-secret`. Configure them without exposing the value:

```bash
uv run python scripts/configure_higgsfield_env.py
```

Then run the billable smoke test:

```bash
uv run python examples/higgsfield_seedance_25/main.py
```

It requests the prompt `A cinematic scene at sunset` at 5 seconds, 720p, 16:9, waits for terminal completion via the official SDK's synchronous `subscribe()`, and prints a video URL only on success.

Tracked launch plan:

`examples/production/rbl-launch-video-plan.json`

The plan targets approximately 20 seconds across five 4-second vertical shots with a US$20 project cap and is now bound to the live-verified `bytedance/seedance-2.5/text-to-video` application.

The API prepaid USD balance is separate from Higgsfield creator/plugin credits. Account funding/key creation is an external prerequisite when the active tool surface cannot perform Higgsfield Cloud payment/account mutations.

**Publication remains blocked after generation.** The final cut must enter `PENDING_HUMAN_REVIEW`. Only explicit human confirmation can produce `APPROVED_FOR_PUBLICATION`; Phase 4A contains no automatic social-posting method.

Authority: `docs/production/PHASE_4A_HIGGSFIELD_API_LAUNCH.md`.

## Phase 4C — generate the first launch review cut

The official Seedance 2.5 smoke test has completed successfully in the owner environment after funding the separate Higgsfield API balance.

Generate the five tracked 9:16 shots:

```bash
uv run python scripts/generate_rbl_launch_video.py
```

The generator is resumable and does not automatically retry billable requests. Successful clips are downloaded into ignored `.production/launch-video-outputs/`.

After all five shots are complete, assemble the local review cut:

```bash
uv run python scripts/assemble_rbl_launch_video.py
```

This requires local `ffmpeg` and `ffprobe`. The expected review file is:

`.production/launch-video-outputs/rbl-launch-review.mp4`

Successful assembly sets live state to `PENDING_HUMAN_REVIEW`; it does not authorize or perform social publication.

Authority: `docs/production/PHASE_4C_LAUNCH_VIDEO.md`.


## Phase 5 — direct social publishing

Phase 5 adds a local persistent schedule queue and direct official platform adapters:

```text
final platform exports
-> validated Phase 5 post manifest
-> timezone-aware local schedule queue
-> Instagram / TikTok / YouTube API
-> per-platform publication receipt
```

Supported targets:

- Instagram Reels;
- TikTok Direct Post;
- YouTube vertical video / Shorts-compatible uploads.

The implementation lives under `src/rbl_content_engine/publishing/` and uses only the Python standard library.

Example manifest:

`examples/production/social-post-manifest.example.json`

Validate locally without any network call:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing preflight \
  examples/production/social-post-manifest.example.json
```

Schedule a real post manifest:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing schedule .production/my-post.json
```

Run the due queue once:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing tick
```

Or run continuously:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing daemon --poll-seconds 30
```

Live queue state, OAuth refresh state, final exports, and publication receipts remain under ignored `.production/` paths.

Provider developer-console/OAuth setup is still a one-time external prerequisite. Instagram uses Instagram Login with `instagram_business_basic` + `instagram_business_content_publish` and a publicly reachable HTTPS `video_url`. TikTok additionally requires current Creator Info, explicit per-post consent, editable metadata before consent, Music Usage Confirmation, and a clean API export without application-added promotional logo/watermark/branding.

Authority: `docs/production/PHASE_5_DIRECT_SOCIAL_PUBLISHING.md`.

## Later learning loop

Phase 0 uses manually refreshed market snapshots only. A later phase may compare content archetypes against explicitly authorized first-party account performance so recommendations become specific to the creator's actual audience instead of relying only on generic platform assumptions.
