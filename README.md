# RBL Content Engine

Evidence-driven manual content pipeline for RBL Productions.

## Current scope: Phase 0 manual pilot

Phase 0 turns verified project/GitHub evidence into platform-native content drafts while keeping factual evidence and market strategy separate:

```text
project/GitHub evidence
  -> extracted claims
  -> evidence verification

human direction brief
+ dated platform research
  -> platform strategy

verified claims + strategy
  -> YouTube / Instagram / TikTok treatments
  -> verifier report
  -> storyboard(s)
  -> HUMAN APPROVAL
```

The repository deliberately stops at human approval. It does **not** publish content, message customers, spend money, call paid APIs, perform live trend research, automate video creation, or integrate ProofLab.

## Core idea

The engine separates two questions:

- **What are we allowed to say?** Project evidence and claim verification decide this.
- **How should we tell the story on this platform?** A human direction brief plus a dated platform-research snapshot decide this.

Market research may influence the hook, pacing, format, visual treatment, and audience strategy, but it can never be used to invent or validate a project fact.

## Non-negotiable rules

- Every factual project claim must trace to project evidence.
- Unsupported claims must be flagged and must block a publish-ready result.
- Project evidence references must survive the full pipeline.
- Platform strategy must retain snapshot/date/source lineage.
- Never promise or imply guaranteed views, virality, reach, or algorithmic preference.
- Human approval is always required before publication.
- No secrets or credentials belong in the repo.
- Prefer Python standard library and deterministic logic over frameworks or agents.
- No social posting or customer messaging actions.
- No live platform/API research in the Phase 0 runner.
- No video automation in Phase 0.
- No ProofLab integration in Phase 0.

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
│   └── codex-phase-0-prompt.md
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
│       └── __init__.py
└── tests/
```

Codex should implement Phase 0 from `docs/codex-phase-0-prompt.md`, while treating `AGENTS.md` and `docs/phase-0-spec.md` as authoritative constraints.

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

The project intentionally starts dependency-free. Add a dependency only when the standard library cannot reasonably satisfy a concrete Phase 0 requirement, and document why.

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

## Later learning loop

Phase 0 uses manually refreshed market snapshots only. A later phase may compare content archetypes against explicitly authorized first-party account performance so recommendations become specific to the creator's actual audience instead of relying only on generic platform assumptions.
