# Phase 0 Specification — Manual Evidence-to-Content Pilot

## Purpose

Prove the smallest useful RBL Content Engine workflow before adding automation. Phase 0 is a local/manual pipeline that converts explicit project evidence into a human-reviewable, platform-native content package while preserving factual traceability and strategy lineage.

The system must answer two different questions without mixing them:

1. **What are we allowed to say?** — answered by project evidence and claim verification.
2. **How should we tell the story here?** — answered by a human direction brief plus dated platform research.

## Pipeline

```text
local/project evidence
  -> manually curated claim manifest
  -> deterministic evidence verification

manual direction brief
+ dated local platform research snapshot
  -> deterministic platform strategy/content plan

verified claims + platform strategy
  -> deterministic platform-native drafts
  -> verifier report
  -> deterministic storyboard(s)
  -> PENDING_HUMAN
```

“Extracted claims” in Phase 0 means a human or coding agent creates the claim manifest from inspected evidence. Phase 0 does **not** need an LLM to discover claims.

“Platform intelligence” in Phase 0 means a human periodically researches platforms and checks a dated snapshot into the repository. The runner does **not** browse the web or fetch live trends.

## Technical approach

Use Python 3.11+ and the standard library only unless a dependency is clearly justified in the PR. Plain UTF-8 text/Markdown and JSON are sufficient.

A minimal implementation may use:

```text
src/rbl_content_engine/
  __init__.py
  __main__.py
  pipeline.py

tests/
  test_pipeline.py

examples/taskpebble/
  evidence.md
  claims.json
  direction.json
  output/                 # generated, gitignored

research/platforms/
  2026-08-21/
    platforms.json
```

Do not create a database, web service, queue, agent framework, vector store, browser automation, social integration, analytics integration, or model integration for Phase 0.

## Evidence domains

### Project evidence

Project evidence is authoritative for factual project claims. It is local UTF-8 evidence, typically copied or curated from project/GitHub material before running the pipeline.

### Platform research

Platform research is authoritative only for the strategy guidance recorded in the snapshot. It can influence:

- target audience hypothesis;
- platform/format selection;
- content archetype;
- hook style;
- story structure;
- pacing;
- title/thumbnail concepts;
- visual direction;
- share/save/search/conversation goals.

It **cannot** support a factual statement about the project.

Never merge the two evidence domains into one generic “evidence” object.

See `docs/platform-intelligence.md` for the detailed boundary.

## Project evidence model

Evidence is a local UTF-8 file. Claims reference evidence by repository-relative path and 1-based inclusive line range.

Example reference:

```json
{
  "path": "examples/taskpebble/evidence.md",
  "start_line": 5,
  "end_line": 5,
  "quote": "TaskPebble stores tasks in a local JSON file."
}
```

A reference is valid only when:

1. `path` resolves to a regular file inside the repository/workspace root;
2. `start_line` and `end_line` are valid 1-based inclusive bounds;
3. `start_line <= end_line`;
4. `quote` is non-empty; and
5. `quote` occurs verbatim inside the referenced line range.

Do not fetch evidence from the network in the Phase 0 runner. GitHub evidence can be saved/copied into a local evidence file by the human before running the pipeline.

## Claim model

Recommended minimum manifest shape:

```json
{
  "project": "TaskPebble",
  "claims": [
    {
      "id": "claim-001",
      "text": "TaskPebble stores tasks in a local JSON file.",
      "evidence": [
        {
          "path": "examples/taskpebble/evidence.md",
          "start_line": 5,
          "end_line": 5,
          "quote": "TaskPebble stores tasks in a local JSON file."
        }
      ]
    }
  ]
}
```

Claim IDs must be unique and stable. Preserve input order.

A claim is `SUPPORTED` only when it has at least one evidence reference and every attached evidence reference validates. Otherwise it is `UNSUPPORTED`.

If any input claim is unsupported, the overall project verification status is `BLOCKED`.

## Platform research snapshot

Phase 0 consumes one explicit local snapshot path. The checked-in demo snapshot is:

```text
research/platforms/2026-08-21/platforms.json
```

The snapshot must contain at least:

- snapshot version;
- research date;
- region;
- niche/context;
- global strategy rules;
- one record for each supported platform;
- audience intent;
- current distribution/trend signals;
- recommended archetypes;
- format-specific treatment guidance;
- anti-patterns to avoid;
- source title/publisher/URL/access date.

The snapshot is a dated hypothesis set. The runner must not describe it as live or guaranteed current market truth.

### Snapshot validation

At minimum validate deterministically:

1. required top-level fields exist;
2. `research_date` is a valid ISO date string;
3. platforms requested by the direction brief exist in the snapshot;
4. every platform has at least one source;
5. every source has non-empty `title`, `publisher`, `url`, and `accessed_on`;
6. platform strategy arrays used by the generator are non-empty;
7. the snapshot path resolves inside the workspace root.

Do not make HTTP requests to validate source URLs in Phase 0.

A missing/invalid strategy snapshot should make the platform plan `BLOCKED_STRATEGY`, while project-claim verification remains a separate status.

## Direction brief

Phase 0 uses a local human-authored direction brief such as:

```text
examples/taskpebble/direction.json
```

It must contain:

- project name;
- objective;
- audience hypothesis;
- creative direction;
- one or more requested platform/format targets;
- approval state fixed to `PENDING_HUMAN`.

A target minimally contains:

```json
{
  "platform": "instagram",
  "format": "reels",
  "enabled": true,
  "desired_output": "short-form script and storyboard"
}
```

The direction brief may change how a fact is framed, ordered, visualized, or emphasized. It must not change the factual meaning of a verified claim.

The human direction brief wins over a generic platform recommendation when the two conflict, provided the direction does not violate factual or safety constraints. Preserve the override visibly in the generated strategy artifact.

## Content plan / Content Director

The Phase 0 “Content Director” is deterministic. It is not an autonomous agent or LLM.

For every enabled target, combine:

- supported claims;
- human objective/audience/creative direction;
- matching platform/format strategy;

into a platform-specific treatment.

The same project should not receive identical copy for all platforms. Differences should be deterministic and meaningful, for example different:

- hook framing;
- content archetype;
- pacing guidance;
- visual emphasis;
- CTA/ending style;
- long-form outline versus short-form script structure.

The generator must never invent a factual project statement merely to make a platform treatment more exciting.

## Required TaskPebble treatments

The checked-in `direction.json` requests four treatments.

### YouTube long-form

Produce a concept rather than a full long-form production script. Include at minimum:

- strategy goal;
- recommended archetype;
- 2–3 deterministic title concepts that contain no unsupported project facts;
- opening hook;
- concise section outline;
- claim/evidence references attached to factual outline beats;
- platform snapshot/date lineage.

### YouTube Shorts

Produce a short-form script/storyboard optimized as a self-contained discovery story. It should have an immediate hook, concise proof/demo, and payoff.

### Instagram Reels

Produce a short-form script/storyboard that prioritizes an original, visually legible, share/save-worthy treatment with a strong first-frame promise.

### TikTok

Produce a short-form script/storyboard that prioritizes natural language, curiosity, real process, demonstration, and conversation/search-friendly framing.

These are strategic defaults, not claims that a format will achieve more views.

## Factual language rule

Any generated sentence that states a factual project property must be attributable to one or more `SUPPORTED` claim IDs.

Generic creative language that does not assert a project fact can be unattributed, for example:

- “Here’s the problem.”
- “So I tried a different approach.”
- “Let’s look at the result.”

Do not create implied results, metrics, users, customers, performance improvements, timelines, motivations, or failures unless they are represented by supported claims.

## Content plan output

Generate a human-readable `content-plan.md` containing:

- project;
- objective;
- audience hypothesis;
- research snapshot path/date;
- one section per enabled target;
- platform goal;
- selected content archetype;
- hook/packaging guidance;
- relevant trend/distribution signals;
- strategy source lineage;
- human direction overrides, if any;
- explicit disclaimer that recommendations do not guarantee reach/views.

## Draft outputs

Prefer a predictable target directory structure:

```text
output/
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

A smaller equivalent structure is acceptable if artifact names remain explicit and deterministic.

### Short-form scripts

Each short-form target must:

- use supported claims only for factual beats;
- include a platform-native hook template;
- preserve source claim ID/evidence references next to factual beats;
- preserve platform snapshot/date lineage;
- contain no guarantee of views, virality, or reach;
- be visibly marked blocked/not publish-ready if project or strategy verification is blocked.

### Long-form concept

The long-form output is intentionally only a concept/title/hook/outline in Phase 0. Do not build a full long-form video automation system.

## Verifier report

The verifier report must be useful to a human reviewer and include separate sections for factual and strategy verification.

### Project claims

Include:

- overall project status: `PASS` or `BLOCKED`;
- each claim ID and text;
- `SUPPORTED` or `UNSUPPORTED` per claim;
- retained project evidence references;
- a specific reason for each invalid/unsupported reference.

### Platform strategy

Include:

- strategy status: `PASS` or `BLOCKED_STRATEGY`;
- snapshot path and research date;
- requested target coverage;
- source lineage retained for each platform;
- a warning when the snapshot is missing/invalid;
- statement that platform strategy is heuristic and does not guarantee reach/views.

### Approval

Always state:

```text
approval_status: PENDING_HUMAN
```

`PASS` means factual inputs and local strategy inputs validated. It does **not** mean approved for publication.

## Storyboards

Generate a deterministic storyboard for each short-form target. One section/row per script beat is enough.

Each factual beat must include:

- beat number;
- voiceover/text;
- source claim ID(s);
- project evidence reference(s);
- suggested visual direction that does not add factual claims;
- target platform/format;
- strategy snapshot/date reference.

A storyboard may vary visual style by platform, but it must not invent screenshots, metrics, people, customer outcomes, or implementation details.

Do not build video generation or editing.

## Approval boundary

Every run ends with:

```text
approval_status: PENDING_HUMAN
```

There is no code path in Phase 0 that changes this to approved or publishes anything.

## Machine-readable run summary

`run.json` should contain at least:

- project name;
- project verification status;
- strategy verification status;
- approval status fixed to `PENDING_HUMAN`;
- counts of supported and unsupported claims;
- research snapshot path/date;
- enabled targets;
- generated artifact paths.

Use stable ordering/formatting so repeated runs are byte-for-byte deterministic where workspace paths permit.

## CLI

The intended command is:

```bash
PYTHONPATH=src python -m rbl_content_engine \
  examples/taskpebble/claims.json \
  --direction examples/taskpebble/direction.json \
  --platform-research research/platforms/2026-08-21/platforms.json \
  --output examples/taskpebble/output
```

The command must require no network access and no secrets.

## Required tests

Use `unittest` unless there is a compelling reason not to.

### Project verification

At minimum prove:

1. a supported claim is classified `SUPPORTED`;
2. a claim with no evidence is classified `UNSUPPORTED`;
3. a claim with a bad quote/range is classified `UNSUPPORTED`;
4. unsupported input makes overall project status `BLOCKED`;
5. project evidence references are retained in reports/scripts/storyboards where relevant;
6. supported and unsupported claims are distinguishable in the same manifest;
7. path traversal/out-of-workspace project evidence is rejected.

### Platform intelligence

Also prove:

8. the checked-in platform snapshot validates;
9. a requested platform missing from the snapshot yields `BLOCKED_STRATEGY`;
10. source lineage is retained in `content-plan.md` and relevant target artifacts;
11. platform research is never accepted as project-claim evidence;
12. identical verified claims produce meaningfully different deterministic YouTube Shorts, Instagram Reels, and TikTok treatments;
13. human direction can override a non-safety strategy default without changing verified claim text;
14. generated copy does not contain prohibited guaranteed-performance wording from the fixture/templates.

### Determinism and approval

Also prove:

15. identical inputs produce identical generated artifact contents;
16. approval status is always exactly `PENDING_HUMAN`;
17. generated target ordering follows direction input order;
18. snapshot and evidence paths cannot escape the workspace root.

Negative tests should mutate temporary copies rather than checking unsupported claims into the successful demo manifest.

## Phase 0 demo

Use:

- `examples/taskpebble/evidence.md`;
- `examples/taskpebble/claims.json`;
- `examples/taskpebble/direction.json`;
- `research/platforms/2026-08-21/platforms.json`.

The successful checked-in claim manifest contains only claims literally supported by the synthetic TaskPebble evidence.

The end-to-end demo must run locally without network access, secrets, API keys, paid services, platform accounts, or social posting permissions.

## Market research refresh process

Phase 0 does not automate this. When the team decides research is stale:

1. manually research current official platform guidance/trend material;
2. create a new date directory rather than silently mutating historical snapshots;
3. record source URLs and access dates;
4. review recommendations as hypotheses rather than guarantees;
5. point the next manual run at the new snapshot.

Historical snapshots may remain for reproducibility.

## Phase 1 — document only, do not implement

A later Phase 1 may automate selected safe preparation and learning steps after the manual pilot is proven, such as:

- reading repository files/commits through an approved GitHub integration;
- proposing candidate claims for human confirmation;
- creating richer script variants from the verified claim set;
- conversational “vibe directing” revisions that change only requested scenes/treatments and re-run factual verification;
- adding structured approval/revision/locked-scene states;
- producing reusable content-package metadata;
- CI checks for evidence traceability;
- scheduled/manual-assisted platform research refreshes with source review;
- importing first-party creator analytics after explicit authorization;
- comparing content archetypes against the creator's own historical baseline;
- recommending future experiments based on observed account performance.

First-party performance data should eventually outrank generic market assumptions when there is enough reliable data, but it should never remove human approval or factual evidence lineage.

Social publishing, customer messaging, video automation, paid model actions, and ProofLab remain separate explicit decisions rather than implicit extensions of Phase 0.
