# Codex Prompt — Implement RBL Content Engine Phase 0

Use this prompt with Codex from the repository root.

---

You are implementing **Phase 0 of the RBL Content Engine** in this repository.

Before changing code, read these files in full:

1. `AGENTS.md`
2. `docs/phase-0-spec.md`
3. `docs/platform-intelligence.md`
4. `README.md`
5. `examples/taskpebble/evidence.md`
6. `examples/taskpebble/claims.json`
7. `examples/taskpebble/direction.json`
8. `research/platforms/2026-08-21/platforms.json`

Treat `AGENTS.md` and `docs/phase-0-spec.md` as authoritative. Do not expand scope beyond them.

## Goal

Implement the smallest evidence-driven, platform-aware manual content pilot:

```text
local/project evidence
-> claim manifest with evidence references
-> deterministic project-claim verification

human direction brief
+ dated local platform research snapshot
-> deterministic platform strategy/content plan

verified claims + platform strategy
-> platform-native drafts
-> verifier report
-> short-form storyboards
-> PENDING_HUMAN
```

This is a manual pilot. Do **not** automate publishing, customer messaging, video creation, paid APIs/models, GitHub ingestion, live trend research, creator analytics ingestion, or ProofLab.

## Critical conceptual boundary

Keep two evidence domains separate:

### Project evidence

Answers: **What factual statements may be made about the project?**

Every factual project statement must trace to a supported claim and local project evidence.

### Platform research

Answers: **How should the verified story be packaged for this platform?**

It may influence audience framing, hook, archetype, pacing, title/thumbnail concepts, visual direction, share/save/search/conversation goals, and structure.

It must never be used to validate or invent a project fact.

Do not create a generic evidence abstraction that allows platform research to satisfy a project claim.

## Required implementation

Build a small Python 3.11+ standard-library-only package under `src/rbl_content_engine/`.

Prefer a compact structure such as:

```text
src/rbl_content_engine/
  __init__.py
  __main__.py
  pipeline.py
```

A small separate module such as `platforms.py` is acceptable if it improves readability. Do not create frameworks, services, databases, agents, queues, vector stores, or network clients.

## CLI

Provide this local command:

```bash
PYTHONPATH=src python -m rbl_content_engine \
  examples/taskpebble/claims.json \
  --direction examples/taskpebble/direction.json \
  --platform-research research/platforms/2026-08-21/platforms.json \
  --output examples/taskpebble/output
```

The command must require no network access and no secrets.

It should generate an explicit deterministic artifact structure equivalent to:

```text
examples/taskpebble/output/
  claims.md
  content-plan.md
  verifier-report.md
  run.json
  youtube-long-form.md
  scripts/
    youtube-shorts.md
    instagram-reels.md
    tiktok.md
  storyboards/
    youtube-shorts.md
    instagram-reels.md
    tiktok.md
```

Equivalent names are acceptable only if they remain obvious and deterministic.

For identical inputs and workspace contents, generated file contents must be deterministic.

## Project evidence verification

Implement the evidence/reference rules exactly as specified in `docs/phase-0-spec.md`.

At minimum validate:

- evidence path is repository/workspace-local and resolves to a regular file;
- line numbers are 1-based inclusive integers;
- line bounds exist and `start_line <= end_line`;
- quote is non-empty;
- quote occurs verbatim within the referenced line range;
- path traversal outside the workspace root is rejected.

A claim is `SUPPORTED` only if it has at least one evidence reference and all attached references validate. Otherwise it is `UNSUPPORTED`.

If any claim is unsupported, overall project verification is `BLOCKED`.

Do not silently repair or reinterpret evidence references.

## Platform snapshot validation

Load the explicit `--platform-research` local JSON file. Do not fetch anything from the network.

Validate at least:

- path remains inside the workspace root;
- required top-level fields exist;
- `research_date` parses as an ISO date;
- every requested platform exists;
- requested formats have usable treatment guidance;
- every requested platform has one or more source records;
- each source has non-empty `title`, `publisher`, `url`, and `accessed_on`;
- strategy arrays used by generation are non-empty.

If strategy validation fails, set strategy status to `BLOCKED_STRATEGY` without changing the independent project-claim status.

Do not make network calls to test whether source URLs are reachable.

## Direction brief validation

Load the explicit `--direction` local JSON file and validate at least:

- project matches the claim manifest project;
- objective is non-empty;
- audience hypothesis is present;
- creative direction is present;
- at least one target is enabled;
- each enabled target has platform, format, and desired output;
- approval status is exactly `PENDING_HUMAN`;
- direction path cannot escape the workspace root.

The human direction may override a generic platform strategy choice, as long as it does not violate evidence or hard safety/scope constraints.

## Content plan

Generate `content-plan.md` before the target drafts.

It must show:

- project;
- objective;
- audience hypothesis;
- research snapshot path and date;
- target order from the direction brief;
- one section per enabled platform/format;
- platform goal;
- selected deterministic archetype;
- hook/packaging guidance;
- relevant strategy signals;
- source lineage;
- any human override applied;
- explicit statement that the strategy does not guarantee views, reach, or virality.

Use simple deterministic selection rules. For example, choose the first recommended archetype compatible with the target unless the direction brief contains an explicit override. Do not implement scoring models or optimization agents.

## Platform-native Content Director

The same verified claims must produce meaningfully different treatments by platform. Do not produce one generic script and swap the platform label.

### YouTube long-form

Generate `youtube-long-form.md` as a **concept**, not a full production script.

Include:

- platform/format;
- strategy goal;
- selected archetype;
- 2–3 deterministic title concepts;
- opening hook;
- concise section outline;
- claim IDs/evidence refs next to factual outline beats;
- platform research snapshot/date/source lineage;
- `approval_status: PENDING_HUMAN`.

Titles/hooks must not add unsupported facts, metrics, outcomes, timelines, or motivations.

### YouTube Shorts

Generate a self-contained short-form discovery treatment.

Use a deterministic template such as:

```text
immediate problem/curiosity hook
-> supported proof/detail beat(s)
-> payoff/summary
-> optional bridge to deeper content
```

Do not assume a trending sound or format guarantees performance.

### Instagram Reels

Generate a short-form treatment with a strong first-frame promise and visually legible proof/payoff.

Use a deterministic template such as:

```text
first-frame promise
-> visual problem/demo
-> supported proof/detail beat(s)
-> clear payoff
-> optional save/share-oriented closing that contains no fake engagement claim
```

Prefer original RBL visual suggestions over repost/remix assumptions.

### TikTok

Generate a conversational, curiosity/process-led treatment.

Use a deterministic template such as:

```text
natural first-sentence hook
-> real problem/process framing
-> supported proof/demo beat(s)
-> result/lesson/open loop
```

Do not fabricate failures, emotions, customer stories, or personal motivations. If the evidence does not say something failed, do not say it failed merely because “failure stories” are a recommended archetype.

## Factual language rule

Any generated sentence that states a factual project property must map to one or more supported claim IDs.

Generic connective language may be unattributed if it does not assert a fact, for example:

- “Here’s the problem.”
- “Let’s look at how this works.”
- “That gives us the core idea.”

Never invent:

- metrics;
- users/customers;
- revenue;
- performance improvements;
- timelines;
- reasons/motivations;
- failures;
- integrations;
- technical details not present in supported claims.

## Claim/evidence output

`claims.md` must preserve, for every claim:

- claim ID;
- claim text;
- support status;
- evidence path;
- line range;
- quote;
- failure reason when unsupported.

## Strategy lineage

Every target artifact must retain at least:

- platform;
- format;
- platform snapshot path;
- research date;
- source titles/URLs or a clear pointer back to the corresponding section of `content-plan.md`.

Market recommendations are hypotheses. Add a short statement that they do not guarantee views/reach/virality.

## Verifier report

`verifier-report.md` must contain separate sections.

### Project verification

- overall project status `PASS` or `BLOCKED`;
- every claim and its `SUPPORTED`/`UNSUPPORTED` status;
- evidence references;
- exact reasons for invalid references.

### Strategy verification

- strategy status `PASS` or `BLOCKED_STRATEGY`;
- snapshot path/date;
- requested target coverage;
- retained source lineage for each platform;
- errors for invalid/missing strategy data;
- statement that market strategy cannot validate project facts;
- statement that strategy does not guarantee reach/views.

### Approval

Always include:

```text
approval_status: PENDING_HUMAN
```

A clean verifier result is not publication approval.

## Storyboards

Generate one deterministic storyboard for each short-form target only:

- YouTube Shorts;
- Instagram Reels;
- TikTok.

Each beat must include:

- beat number;
- target platform/format;
- voiceover/text;
- source claim ID(s) for factual language;
- retained project evidence reference(s);
- visual direction that does not add factual claims;
- platform strategy snapshot/date pointer.

Visual suggestions may differ by platform. Do not generate/edit actual video.

## Machine-readable run summary

`run.json` should contain at least:

- project name;
- project verification status;
- strategy verification status;
- approval status fixed to `PENDING_HUMAN`;
- counts of supported and unsupported claims;
- direction path;
- research snapshot path/date;
- enabled targets in direction order;
- generated artifact paths.

Use stable ordering/formatting.

## Prohibited wording / guarantees

Generated templates must not claim or imply:

- “guaranteed views”;
- “guaranteed reach”;
- “guaranteed virality”;
- “this will go viral”;
- “the algorithm always favors …”;
- any equivalent certainty.

A strategy may say that a treatment is intended to improve audience fit or test a current hypothesis.

## Tests

Use Python `unittest`; do not add test dependencies.

Create deterministic tests under `tests/` covering at least:

### Project evidence

1. supported claim => `SUPPORTED`;
2. missing evidence => `UNSUPPORTED`;
3. bad quote => `UNSUPPORTED`;
4. invalid line range => `UNSUPPORTED`;
5. path traversal/out-of-workspace evidence => rejected/unsupported;
6. one unsupported claim => project status `BLOCKED`;
7. supported and unsupported claims are distinguishable in the same manifest;
8. evidence references survive into relevant reports/scripts/storyboards.

### Platform intelligence

9. checked-in platform snapshot validates;
10. malformed/missing source data => `BLOCKED_STRATEGY`;
11. requested platform missing from snapshot => `BLOCKED_STRATEGY`;
12. platform research cannot be supplied as project evidence;
13. platform strategy lineage survives into content plan and target artifacts;
14. YouTube Shorts, Instagram Reels, and TikTok outputs are not identical and contain platform-specific deterministic structure;
15. YouTube long-form produces concept/title/hook/outline rather than a full video-production system;
16. direction target order is preserved;
17. human direction can override a generic strategy default without changing verified claim meaning;
18. direction and snapshot path traversal are rejected.

### Guardrails / determinism

19. prohibited guaranteed-performance wording does not appear in generated outputs;
20. identical inputs produce identical artifact contents;
21. approval status is always exactly `PENDING_HUMAN`.

Use temporary directories for mutation/negative tests. Do not modify the checked-in successful TaskPebble manifest to contain unsupported claims.

## End-to-end fixture

Use the existing TaskPebble fixture plus the new direction/research inputs.

After implementation, run:

```bash
make check
make test
rm -rf examples/taskpebble/output
PYTHONPATH=src python -m rbl_content_engine \
  examples/taskpebble/claims.json \
  --direction examples/taskpebble/direction.json \
  --platform-research research/platforms/2026-08-21/platforms.json \
  --output examples/taskpebble/output
```

Inspect all generated artifacts manually and confirm:

- all four checked-in TaskPebble claims are supported;
- project evidence references are present;
- project verifier status is `PASS`;
- strategy verifier status is `PASS`;
- strategy source/date lineage is present;
- four requested treatments exist;
- YouTube Shorts, Instagram Reels, and TikTok treatments are meaningfully different;
- no platform treatment contains invented project facts;
- no artifact promises views/virality/reach;
- approval status remains `PENDING_HUMAN`;
- no external side effects occur.

Do not commit generated `examples/taskpebble/output/` files unless there is a strong reason; they should remain reproducible generated artifacts.

## README update

Update `README.md` only as needed to document the final runnable command, artifact meanings, test commands, and actual implementation behavior. Keep it concise.

## Scope exclusions

Do not implement any of the following:

- social platform APIs;
- auto-posting;
- customer DMs/email;
- scheduled publishing;
- paid API/model calls;
- OpenAI/Anthropic/Gemini SDKs;
- browser automation;
- live web/trend research in the runner;
- remote GitHub ingestion;
- Instagram/TikTok/YouTube account analytics ingestion;
- database/storage services;
- embeddings/vector search;
- autonomous agents;
- video generation/editing;
- voiceover generation;
- ProofLab integration;
- auto-approval.

If a proposed feature is not required to satisfy the Phase 0 exit criteria, leave it out.

## Phase 1 — document only

Do not implement Phase 1, but keep the code shape compatible with later additions such as:

- conversational targeted “vibe directing” revisions;
- locked scenes/sections;
- safe platform-research refresh assistance;
- first-party creator analytics after explicit authorization;
- experiments comparing hook/archetype/format against the creator's own historical baseline.

First-party results should eventually be more valuable than generic platform assumptions, but factual project evidence and human approval remain mandatory.

## Definition of done

Phase 0 is done when:

- the CLI completes the TaskPebble run locally;
- all required artifacts are produced;
- supported/unsupported project verification behaves correctly;
- invalid/missing platform strategy is separately detectable;
- project evidence lineage is retained;
- platform strategy lineage is retained;
- outputs are meaningfully platform-native;
- deterministic tests pass;
- human approval is still mandatory;
- there is no publication or external side effect.

At the end, report:

1. files changed;
2. implementation summary;
3. commands/tests run and results;
4. example project and strategy verification results;
5. generated target list;
6. any deliberate Phase 0 limitations left for Phase 1.

Do not claim success unless you actually ran the tests and the end-to-end example.

---
