# AGENTS.md — RBL Content Engine

This repository is intentionally narrow. Optimize for the smallest evidence-driven manual pilot, not for a production content platform.

## Authority order

When instructions conflict, follow this order:

1. `AGENTS.md`
2. `docs/phase-0-spec.md`
3. `docs/platform-intelligence.md`
4. the active task/prompt
5. existing implementation conventions

## Phase 0 boundary

Build only this flow:

```text
project/GitHub evidence
-> claims with evidence references
-> deterministic claim verification

manual direction brief + dated local platform research
-> platform-specific strategy

verified claims + strategy
-> platform-native drafts/storyboards
-> verifier report
-> pending human approval
```

Do not cross the human-approval boundary.

## Two evidence domains

Keep these domains separate at all times:

### Project evidence

Determines **what factual claims are allowed** about a project. Every factual project claim must trace to valid project evidence.

### Platform research

Determines **how verified facts may be packaged** for a target platform: audience intent, hook, format, pacing, story structure, visual treatment, and content archetype.

Platform research is not evidence for project facts. Never use a market trend or platform statistic to validate or invent a project claim.

## Hard constraints

- No automatic social publishing.
- No customer messaging.
- No paid API calls or paid model usage.
- No invented factual project claims.
- Every factual project claim must trace to project evidence.
- Unsupported claims must be visibly flagged and must block a clean verification result.
- Evidence references must remain attached through generated outputs.
- Platform strategy must retain its research snapshot path/date/source lineage.
- Never claim or imply guaranteed views, reach, virality, or algorithmic preference.
- Human approval must remain required; code must never auto-approve.
- Human direction may override strategy recommendations before approval.
- No secrets, tokens, credentials, or `.env` values.
- No video generation/editing automation.
- No ProofLab integration.
- No network requirement for the Phase 0 demo or tests.
- The Phase 0 runner must not perform live trend research; it consumes a checked-in/manual local snapshot.

## Engineering defaults

- Python 3.11+.
- Prefer the standard library. Do not add dependencies unless a concrete requirement cannot reasonably be met without one.
- Prefer plain files and explicit data structures over databases, queues, agent frameworks, vector stores, or orchestration systems.
- Keep deterministic logic deterministic: stable ordering, stable filenames, stable formatting.
- Tests are required for deterministic verification/generation logic.
- A synthetic/public-safe fixture is the only project evidence used by the checked-in demo.
- Generated files must be inspectable by a human without special tooling.
- Treat platform profiles as dated strategy inputs, not timeless truths.

## Expected implementation size

Phase 0 should fit comfortably in a small package with a few focused modules. If the solution starts needing services, workers, external APIs, or a large dependency graph, the design has drifted out of scope.

## Required Phase 0 inputs

The checked-in demo uses:

- `examples/taskpebble/evidence.md` — synthetic project evidence;
- `examples/taskpebble/claims.json` — manually curated claims;
- `examples/taskpebble/direction.json` — human objective/audience/creative direction and target formats;
- `research/platforms/2026-08-21/platforms.json` — dated manual platform strategy snapshot.

## Definition of done

A local command can run one synthetic/public-safe fixture end-to-end and produce:

1. evidence/claim set;
2. platform strategy/content plan;
3. platform-native draft treatments for requested targets;
4. verification report;
5. storyboard(s) for short-form targets;
6. approval status `PENDING_HUMAN`.

At minimum the TaskPebble demo should distinguish:

- YouTube long-form concept/outline;
- YouTube Shorts draft;
- Instagram Reels draft;
- TikTok draft.

Tests prove that unsupported claims are flagged, project evidence references are retained, platform strategy lineage is retained, supported/unsupported claims are distinguished correctly, platform outputs differ in meaningful deterministic ways, and deterministic outputs remain stable.
