# AGENTS.md — RBL Content Engine

This repository is intentionally narrow. Optimize for the smallest evidence-driven manual pilot, not for a production content platform.

## Authority order

When instructions conflict, follow this order:

1. `AGENTS.md`
2. `docs/phase-0-spec.md`
3. the active task/prompt
4. existing implementation conventions

## Phase 0 boundary

Build only this flow:

```text
project/GitHub evidence
-> claims with evidence references
-> draft short-form script
-> verifier report
-> storyboard
-> pending human approval
```

Do not cross the human-approval boundary.

## Hard constraints

- No automatic social publishing.
- No customer messaging.
- No paid API calls or paid model usage.
- No invented factual project claims.
- Every factual claim must trace to evidence.
- Unsupported claims must be visibly flagged and must block a clean verification result.
- Evidence references must remain attached through generated outputs.
- Human approval must remain required; code must never auto-approve.
- No secrets, tokens, credentials, or `.env` values.
- No video generation/editing automation.
- No ProofLab integration.
- No network requirement for the Phase 0 demo or tests.

## Engineering defaults

- Python 3.11+.
- Prefer the standard library. Do not add dependencies unless a concrete requirement cannot reasonably be met without one.
- Prefer plain files and explicit data structures over databases, queues, agent frameworks, vector stores, or orchestration systems.
- Keep deterministic logic deterministic: stable ordering, stable filenames, stable formatting.
- Tests are required for deterministic verification/generation logic.
- A synthetic/public-safe fixture is the only evidence used by the checked-in demo.
- Generated files must be inspectable by a human without special tooling.

## Expected implementation size

Phase 0 should fit comfortably in a small package with a few focused modules. If the solution starts needing services, workers, external APIs, or a large dependency graph, the design has drifted out of scope.

## Definition of done

A local command can run one synthetic/public-safe fixture end-to-end and produce:

1. evidence/claim set;
2. draft script;
3. verification report;
4. storyboard;
5. approval status `PENDING_HUMAN`.

Tests prove that unsupported claims are flagged, evidence references are retained, supported/unsupported claims are distinguished correctly, and deterministic outputs remain stable.
