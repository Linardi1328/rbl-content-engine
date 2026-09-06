# RBL Topview Production Workflow

## Purpose

This document defines how RBL Content Engine uses Topview as a controlled visual-production and rendering subsystem.

Codex is the **RBL Topview Production Operator**. Codex performs production operations from an approved RBL production contract; it is not the creative director and must not silently redesign approved creative decisions.

The operating principle is:

> RBL decides. Topview renders. QC evaluates. Human approves.

Phase 1 is a contract/documentation milestone only. It does not authorize paid Topview generation, video automation, publishing, or any action forbidden by `AGENTS.md` or `docs/phase-0-spec.md`.

## Inputs and handoff

The intended long-term handoff is:

```text
sources / evidence
-> verified claims
-> content brief
-> platform treatment
-> script
-> shot manifest
-> Topview Production Manifest
-> Codex + Topview MCP
-> controlled production
-> human approval
```

Project evidence continues to control **what RBL is allowed to claim**. The Topview production contract controls **how an approved visual treatment is produced**. Visual generation must never invent or validate project facts.

## Creative-freedom gradient

Model freedom should decrease as production progresses:

```text
early ideation             high freedom
script                     less freedom
storyboard / keyframe      constrained
locked references          low freedom
video generation           animate approved composition
final edit                 minimal creative freedom
```

Once a reference, storyboard, or production decision is human-approved, later phases must preserve it unless a human explicitly unlocks or replaces it.

## Canonical phases

### Phase 0 — PREFLIGHT

Goal: prove the production environment is usable **before** any chargeable operation.

Preflight must determine, using the live Topview MCP surface when available:

- the Topview MCP is connected and responsive;
- the intended Topview account is authenticated;
- the intended Canvas/project can be accessed;
- required Canvas ownership/permissions are sufficient for planned operations;
- required references/assets are accessible;
- required generation capabilities and model families are currently available;
- current generation configuration and billing hints are understood;
- task monitoring is available;
- timeline/export capabilities required by the project are available or explicitly marked manual;
- the planned spend fits the RBL budget guardrail.

If permission or ownership cannot be established safely, stop. Do not discover authorization failures by attempting a paid generation.

Known hard-stop example:

```text
Only canvas owner can perform this operation.
```

Treat an authentication/permission failure as a production blocker, not as a creative failure.

### Phase 1 — CANVAS SETUP

Goal: establish the remote production container and record its identifier in local production state.

Codex may create/select the Canvas/project only after preflight succeeds. Naming and identifiers must be recorded immediately.

### Phase 2 — REFERENCES

Goal: register authoritative production assets.

Examples:

- `REF_CHARACTER_A`
- `REF_CHARACTER_B`
- `REF_PRODUCT`
- `REF_UNIFORM`
- `REF_LOCATION_A`
- `REF_STYLE_MASTER`

Each reference needs an RBL reference ID, source/remote asset ID where applicable, type, approval state, and lock state.

Human-approved references become **LOCKED**. Locked references must not be silently redesigned, swapped, restyled, or regenerated later.

### Phase 3 — STYLE

Goal: establish the approved visual language for the production.

Style may reference a locked master style asset plus written constraints. Style decisions cannot override locked character/product identity or project-fact constraints.

### Phase 4 — ENVIRONMENTS

Goal: establish reusable locations/backgrounds before shot generation.

Environment identity and continuity should be explicit when a sequence returns to the same location.

### Phase 5 — SCENECARDS

Goal: translate the approved script/shot manifest into production units.

A SceneCard should capture at least:

- scene ID and purpose;
- duration target;
- required references;
- shot composition and camera intent;
- action intent;
- entry state;
- exit state;
- generation method preference;
- storyboard requirements;
- continuity constraints;
- QC constraints;
- approval gates;
- factual/evidence lineage for spoken or on-screen claims.

The manifest is the canonical machine-readable representation; any Topview-specific SceneCard object is an execution projection of that contract.

### Phase 6 — STORYBOARD / KEYFRAMES

Goal: approve composition before expensive motion generation.

For important shots, prefer:

```text
locked references
-> shot-specific storyboard/keyframe
-> human approval
-> image-to-video
```

Do not default to many independent references plus a complex text-to-video prompt and expect the model to reconstruct an approved composition.

If `start_frame_required` is true, a human-approved start frame is required before video generation. End frames may also be required for continuity-sensitive transitions.

### Phase 7 — 720P VIDEO DRAFT

Goal: test motion, action, composition, and continuity at lower cost.

Default controlled AI-generated clip length: **4–8 seconds**.

Longer continuous generated shots should be exceptional and need an explicit creative/risk justification. Model-specific maximum durations must always be resolved from live capabilities rather than assumed.

Use 720p for motion/composition testing where the live model supports it. Do not spend on final-resolution generation before the shot passes QC and the required human gate.

### Phase 8 — QC

Goal: determine whether the draft is KEEP, FIX, or REJECT.

Minimum QC dimensions:

- approved character identity preserved;
- approved product/object identity preserved;
- no duplicated approved characters;
- no duplicated faces or bodies;
- no duplicate unique jersey/person identity;
- no mirrored clones;
- object-count constraints satisfied;
- environment continuity preserved;
- composition is consistent with the approved storyboard;
- anatomy is acceptable;
- action logic is physically/narratively coherent;
- entry/exit continuity is coherent;
- camera/action intent is satisfied;
- factual on-screen text/narration remains within approved evidence lineage.

QC records evidence and a disposition. It does not grant publication approval.

### Phase 9 — TARGETED EDIT / REGENERATION

Goal: repair the smallest incorrect layer instead of blindly regenerating a mostly-correct shot.

Use this failure hierarchy:

| Level | Failure | Default action |
|---|---|---|
| 1 | Cosmetic: lighting, background density, minor ambience | targeted video edit when a verified live tool supports it |
| 2 | Local action: orientation, hand position, object placement | targeted video edit when appropriate |
| 3 | Structural motion: impossible physics, duplicate identity, wrong action sequence | regenerate video from approved keyframe |
| 4 | Composition | regenerate storyboard/keyframe first |
| 5 | Reference | repair/replace reference, then re-approve and re-lock |
| 6 | MCP auth/permission | stop production; resolve authentication/ownership first |

Never invent a `video_edit` tool name. `docs/topview/TOOL_MAP.md` and live MCP discovery determine whether targeted editing is currently executable.

### Phase 10 — FINAL 1080P GENERATION

Goal: finalize only approved motion/composition.

A shot may advance to final resolution only after required draft QC and human approval. Use 1080p when supported and justified by the destination. A live model may expose different resolution options; the live configuration is authoritative.

### Phase 11 — TIMELINE / AUDIO

Goal: assemble approved shots and approved audio elements without re-opening visual creative decisions.

Timeline, audio, voice, music, caption, and transition operations must preserve scene order, approved timing intent, evidence constraints, and budget limits.

If the currently installed Topview MCP does not expose required timeline operations, mark them `MANUAL_REQUIRED`; do not guess APIs.

### Phase 12 — EXPORT

Goal: create the reviewable final media artifact.

Export is not publication. Exported artifacts remain subject to final human approval.

### Phase 13 — HUMAN APPROVAL

Goal: explicit final decision by the human owner/director.

Final publication status must remain human-controlled. No previous approval implies publication approval.

## Approval gates

Important stages require explicit gates:

```text
REFERENCE APPROVAL
-> STORYBOARD / KEYFRAME APPROVAL
-> 720P VIDEO APPROVAL
-> FINAL 1080P
-> TIMELINE APPROVAL
-> EXPORT / PUBLICATION APPROVAL
```

Approval has scope. For example:

- approving a reference allows downstream use of that locked reference;
- approving a storyboard allows draft motion generation;
- approving a 720p draft allows final-resolution generation;
- approving a timeline allows export;
- only final human publication approval may cross the publication boundary.

Codex must not reinterpret one gate as approval for later gates.

## Continuity contract

Every continuity-sensitive scene must support explicit `entry_state` and `exit_state`.

State categories include:

- characters/identities;
- position;
- clothing/uniform;
- object state/count;
- environment;
- camera direction;
- emotional state.

Where continuity is required, scene `S(n+1).entry_state` must logically follow `S(n).exit_state`.

Example:

```text
S09 exit: Player #23 releases the basketball from the right corner toward Basket A.
S10 entry: the same basketball is travelling toward Basket A from the right-corner trajectory.
```

An unrelated celebration shot would fail continuity even if it is visually attractive.

## Production state and resumability

The manifest describes **intended production**. `.production/topview-state.json` describes **observed execution state**.

Persist remote identifiers and status immediately after successful operations so a later Codex session can resume without reconstructing history from chat.

The live state file is local mutable state and must not be committed to this public repository. Use the tracked example/schema as the design contract.

State should capture at least:

- project ID and current phase;
- Canvas/project ID;
- preflight result;
- reference/style/environment statuses;
- current scene;
- scene statuses;
- approval currently required;
- generated task IDs;
- approved output IDs;
- model/config resolutions actually used;
- budget estimates and actual spend where known;
- failure/recovery notes.

## Tool discovery rule

MCP capability does not equal workflow knowledge, and historical tool names do not equal current tool names.

Before executing Topview operations in a Codex environment:

1. discover the live installed Topview MCP tools and schemas;
2. compare them against `docs/topview/TOOL_MAP.md`;
3. resolve model IDs/options from the live generation configuration;
4. record capability gaps;
5. stop rather than guess an operation that is not verified live.

Public Topview documentation can establish `OFFICIAL_DOC` status but only the active Codex/MCP environment can establish `VERIFIED_LIVE`.

## Budget policy

The existing RBL video-production budget guardrail remains authoritative:

- target approximately US$60/month;
- normal prototype cap US$100/month;
- absolute prototype ceiling US$150/month unless explicitly changed by the human owner;
- failed generations and retries count against the same budget;
- prefer existing footage/assets and low-cost draft methods before premium generation;
- premium generation needs an explicit reason and estimated cost.

Phase 1 does not authorize any paid generation.

## Non-goals for Phase 1

Do not implement yet:

- a production API adapter;
- automatic Topview tool execution;
- paid generation;
- video-edit calls;
- timeline automation;
- publishing;
- autonomous approval;
- autonomous creative direction;
- full QC computer vision.

The Phase 1 deliverable is the contract that future execution code and Codex sessions must follow.
