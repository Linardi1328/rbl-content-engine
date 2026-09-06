# RBL Content Engine

Evidence-driven manual content pipeline for RBL Productions.

## Current scope: Phase 0 manual pilot

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
│       └── DISCOVERY.md             # Phase 1B live MCP discovery procedure
├── schemas/
│   ├── topview-production.schema.json
│   ├── topview-state.schema.json
│   └── topview-capabilities.schema.json
├── .production/
│   ├── topview-state.example.json
│   └── topview-capabilities.example.json
├── research/
│   └── platforms/
│       └── 2026-08-21/
│           └── platforms.json
├── examples/
│   └── taskpebble/
│       ├── evidence.md
│       ├── claims.json
│       └── direction.json
├── src/
│   └── rbl_content_engine/
│       ├── __init__.py
│       ├── prooflab.py              # local fail-closed factual contract
│       ├── ai_generation.py         # provider-neutral generation contract
│       └── topview/
│           ├── validator.py         # Phase 1C semantic contract validation
│           ├── preflight.py         # Phase 1C fail-closed readiness evaluator
│           └── __main__.py          # local CLI; no external calls
└── tests/
```

Codex should implement Phase 0 from `docs/codex-phase-0-prompt.md`, while treating `AGENTS.md` and `docs/phase-0-spec.md` as authoritative constraints. Topview work must also follow `docs/topview/WORKFLOW.md`, `docs/topview/TOOL_MAP.md`, and `docs/topview/DISCOVERY.md`.

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

Commands:

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

## Later learning loop

Phase 0 uses manually refreshed market snapshots only. A later phase may compare content archetypes against explicitly authorized first-party account performance so recommendations become specific to the creator's actual audience instead of relying only on generic platform assumptions.
