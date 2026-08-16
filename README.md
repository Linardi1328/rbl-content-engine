# RBL Content Engine

Evidence-driven manual content pipeline for RBL Productions.

## Current scope: Phase 0 manual pilot

Phase 0 turns project/GitHub evidence into a human-reviewable short-form content package:

```text
project/GitHub evidence
  -> extracted claims
  -> evidence references
  -> draft short-form script
  -> verifier report
  -> storyboard
  -> HUMAN APPROVAL
```

The repository deliberately stops at human approval. It does **not** publish content, message customers, spend money, call paid APIs, automate video creation, or integrate ProofLab.

## Non-negotiable rules

- Every factual claim must trace to evidence.
- Unsupported claims must be flagged and must block a publish-ready result.
- Evidence references must survive the full pipeline.
- Human approval is always required before publication.
- No secrets or credentials belong in the repo.
- Prefer Python standard library and deterministic logic over frameworks or agents.
- No social posting or customer messaging actions.
- No video automation in Phase 0.
- No ProofLab integration in Phase 0.

## Intended repository shape

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml
├── Makefile
├── docs/
│   ├── phase-0-spec.md
│   └── codex-phase-0-prompt.md
├── examples/
│   └── taskpebble/
│       └── evidence.md
├── src/
│   └── rbl_content_engine/
│       └── __init__.py
└── tests/
    └── fixtures/
```

Codex should implement Phase 0 from `docs/codex-phase-0-prompt.md`, while treating `AGENTS.md` and `docs/phase-0-spec.md` as authoritative constraints.

## Development

Target runtime: Python 3.11+.

```bash
make check
make test
```

The project intentionally starts dependency-free. Add a dependency only when the standard library cannot reasonably satisfy a concrete Phase 0 requirement, and document why.

## Phase 0 exit criteria

A single manual end-to-end run using synthetic/public-safe evidence must produce:

- an evidence/claim set;
- a draft short-form script;
- a verifier result;
- a storyboard;
- a pending human-approval state;

with no publication or other external side effects.
