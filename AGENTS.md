# AGENTS.md — RBL Content Engine

This repository is intentionally narrow. Optimize for the smallest evidence-driven manual pilot, not for a production content platform.

## Authority order

When instructions conflict, follow this order:

1. `AGENTS.md`
2. `docs/phase-0-spec.md`
3. `docs/platform-intelligence.md`
4. for Topview production tasks, `docs/topview/WORKFLOW.md`
5. for Topview capability/tool routing, `docs/topview/TOOL_MAP.md`
6. for live Topview capability discovery, `docs/topview/DISCOVERY.md`
7. for the controlled preflight/reference pilot, `docs/topview/PHASE_1D_PILOT.md`
8. the active task/prompt
9. existing implementation conventions

Topview documentation never overrides the Phase 0 hard constraints below unless the human owner explicitly changes the project phase/scope.

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
- The local ProofLab verification contract in `src/rbl_content_engine/prooflab.py` is permitted and is the fail-closed factual boundary for future generation contracts.
- No external ProofLab service, network integration, or paid ProofLab dependency is authorized unless explicitly added in a later phase.
- No network requirement for the Phase 0 demo or tests.
- The Phase 0 runner must not perform live trend research; it consumes a checked-in/manual local snapshot.

The local ProofLab contract does not expand Phase 0 into external ProofLab automation; it formalizes the existing local claim-verification boundary introduced on `main`.

## Topview production operator contract

Phase 1 may define and exercise non-chargeable production-control contracts without enabling paid/video execution.

For any Topview-related task:

- Codex acts as **RBL Topview Production Operator**, not creative director.
- Read `docs/topview/WORKFLOW.md`, `docs/topview/TOOL_MAP.md`, and `docs/topview/DISCOVERY.md` before planning or executing Topview operations. Read `docs/topview/PHASE_1D_PILOT.md` before the controlled preflight/reference pilot.
- Topview is downstream of the local ProofLab boundary. Factual content must already be represented by `VerifiedClaim` values that pass `require_verified_claims()` before it enters a Topview Production Manifest or future Topview execution path.
- Topview may visualize verified facts but must never create, upgrade, reinterpret, or validate unsupported/conflicting project claims.
- Treat human-approved references and keyframes as authoritative; locked assets must not be silently redesigned.
- Prefer approved-keyframe image-to-video for important shots rather than reconstructing composition from many independent references plus a large text prompt.
- Default controlled AI-generated clips to roughly **4–8 seconds**; longer generated shots need an explicit creative/risk justification.
- Use 720p for draft motion/composition testing and only advance to 1080p after the required QC/human gate when the live model supports those resolutions.
- Preserve explicit scene entry/exit state where continuity matters and enforce duplicate/identity/object-count QC constraints.
- Use targeted repair for local/cosmetic failures when a verified live tool supports it; do not blindly regenerate a mostly-correct shot.
- Never guess current Topview tool names, model IDs, permissions, remote asset IDs, or schemas. Public docs establish only `OFFICIAL_DOC`; active MCP discovery establishes `VERIFIED_LIVE`.
- Record actual live discovery in local `.production/topview-capabilities.json`; never commit that file to this public repository.
- Run the dependency-free local validators/preflight in `rbl_content_engine.topview` before any future Topview execution step.
- Phase 1D may inspect non-chargeable live connectivity, account/Canvas permissions, tool schemas, and generation configuration, but it must not submit an image/video generation task.
- Phase 1D reference registration must record only a remote asset ID actually returned by the live Topview session. Successful upload/registration never implies human approval.
- Record the live Phase 1D reference registry in `.production/topview-references.json`; never commit that file to this public repository.
- A locked reference binds the RBL reference ID to its manifest type, local source path, SHA-256 source fingerprint, observed remote Topview asset ID, and explicit human approval. Source drift after locking is a hard stop.
- A validator or preflight result does not authorize spending. Phase 1 CLI intentionally provides no paid-generation authorization switch.
- Authentication/Canvas ownership failures are hard stops. Resolve permissions and repeat preflight before production.
- Maintain resumable execution state in local `.production/topview-state.json`; never commit that live state file to this public repository.
- Approval is scoped. Preflight/reference/storyboard/draft/timeline approval never implies final publication approval.

Phase 1 documentation/schemas/validators/reference tools do **not** authorize any chargeable Topview call while the Phase 0 no-paid-API rule remains active.

## Future video-production budget guardrail

This section applies when paid video generation is introduced in a later phase. It does **not** authorize paid calls in Phase 0.

- Design the early Video Production Agent around a **US$60/month target operating budget**.
- Treat **US$100/month as the normal prototype cap**.
- Treat **US$150/month as the absolute prototype ceiling** unless the human owner explicitly changes the budget.
- Prefer existing real footage, project UI, screen recordings, reusable B-roll, screenshots, and local motion graphics before generating new AI video.
- Use AI video only where it materially improves the shot or cannot reasonably be produced from existing/local assets.
- Prefer lower-cost generation models for drafts and ordinary shots; reserve premium models for clearly justified hero shots.
- Premium generation must have an explicit reason and estimated cost before use.
- As an initial planning default, target no more than roughly **10 seconds of AI-generated footage per finished short-form video** unless a human deliberately overrides it.
- Track estimated and actual spend per generation, per finished video, and per month.
- Re-renders and failed generations count against the same budget; do not treat retries as free.
- Optimize for useful content output and learning per dollar, not maximum synthetic-video quality.
- Never let model routing automatically exceed the configured monthly or per-video budget ceiling.

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
