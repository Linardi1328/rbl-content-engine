# Phase 3A — Provider-Neutral Production Contract

## Purpose

Phase 3A opens the first production-development milestone after accepted Phase 2. It turns the earlier Topview-specific production lessons into a provider-neutral RBL contract.

The operating principle is:

> **RBL owns the production process. Providers render approved production units.**

Higgsfield, Topview, MuAPI, local inference, or future providers may supply rendering capacity. None of them may redefine factual lineage, SceneCards, reference locks, continuity, QC, or approval gates.

Phase 3A is an architecture and readiness milestone. It does **not** submit generation jobs.

## Why this phase exists

The prototype should prove the production loop before RBL commits to a recurring provider plan.

A monthly subscription can be useful once generation volume is predictable, but during early development the main uncertainty is the workflow itself:

- whether SceneCards consistently produce the intended shot;
- how many retries a usable shot needs;
- whether references remain stable;
- how much manual correction is required;
- what an approved video actually costs;
- whether published content provides enough first-party observations to justify scaling.

Free credits, trial credits, launch grants, and low-cost models are therefore tactical prototype capacity. They must never become an architectural dependency.

## Durable production flow

```text
verified project claims / approved non-factual creative brief
-> SceneCard
-> locked references
-> approved storyboard/keyframe
-> provider-neutral generation need
-> provider capability + cost preflight
-> explicit human generation approval
-> renderer/provider
-> RBL QC
-> human approval
-> publication outside the engine
-> production record + first-party observation
-> human learning / next hypothesis
```

Changing the renderer must not require rewriting the upstream RBL methodology.

## Prototype stages

### PROVE_PIPELINE

Goal: produce the first few complete videos end to end at the lowest legitimate cost.

Default policy:

- fewer than 5 completed **and published** prototype videos;
- prefer existing footage, local assets, free/trial allowance, or inexpensive models where appropriate;
- no recurring provider commitment is required;
- every retry must still be recorded;
- publication remains a separate human action.

The objective is production reliability, not proving virality or revenue.

### PROVE_REPEATABILITY

Goal: show that the process can be repeated and measured.

The repository should retain a production record for every completed/published prototype video, including:

- production completion;
- publication status;
- retry count;
- QC record presence;
- actual cost amount and cost unit;
- whether a first-party social observation has been recorded.

At least 5 completed/published videos are required before provider stabilization may be considered.

At least 3 of those videos must also have first-party social observation records.

These thresholds are a versioned prototype policy, not a forecast and not proof that a provider or creative treatment is successful.

### STABILIZE_PROVIDER

Goal: allow a human to decide whether recurring capacity is justified.

The stage is reachable only when:

- at least 5 completed/published prototype videos exist;
- retry data is complete for those videos;
- QC data is recorded;
- actual cost/unit data is recorded;
- at least 3 first-party social observations exist;
- a human explicitly confirms the stability gate.

Reaching this stage does **not** automatically subscribe to Higgsfield, migrate providers, or spend money. It only makes such a decision eligible for a separate explicit human authorization.

## Provider-neutral capability contract

Phase 3A represents provider support with stable RBL capability IDs rather than provider-specific tool names.

Initial capabilities include:

- `keyframe_image`
- `text_to_video`
- `image_to_video`
- `reference_image`
- `start_frame`
- `end_frame`
- `video_edit`
- `cost_estimate`
- `task_monitoring`

A provider is eligible for a production need only when it declares every required capability.

Provider-specific tool/model discovery remains external/live evidence. Never infer a model ID or capability because another provider supports something similar.

## Provider examples

Current known candidate channels include:

- Higgsfield ChatGPT/MCP plugin;
- Higgsfield official API;
- Topview MCP/Canvas;
- MuAPI-backed workflows;
- local/open inference where hardware and licenses allow it.

These are examples, not a fixed provider ranking.

RBL should not hard-code "Higgsfield always wins" or "Topview always wins." Provider choice may change as costs, model quality, quotas, capabilities, or account entitlements change.

## Cost integrity

Provider costs may be denominated in different units:

- USD;
- provider credits;
- one-off free-generation allowances;
- local-compute usage.

Never silently compare unlike units.

A credit-denominated quote cannot enter an RBL cash-budget comparison until an explicit USD estimate/conversion is recorded. The quote must retain its original unit and source.

Retries and failed generations remain part of production cost accounting.

The existing future-video budget guardrail remains:

- target: roughly US$60/month;
- normal prototype cap: US$100/month;
- absolute prototype ceiling: US$150/month unless the human owner changes it.

Those ceilings are guardrails, not spending authorization.

## Credential and free-credit policy

RBL may use legitimate free/trial capacity that belongs to the human owner or an authorized workspace.

RBL must not use:

- API keys copied from public repositories;
- leaked/shared credentials;
- credentials belonging to another user/workspace;
- undocumented bypasses intended to evade provider billing or quotas.

Open-source clients and studios may be studied or reused under their licenses, but their availability does not make hosted inference free.

No credentials, tokens, cookies, `.env` values, short-lived upload URLs, or account secrets belong in tracked repository files.

## Migration invariant

A renderer/provider migration must preserve:

- factual evidence/ProofLab lineage;
- SceneCard intent;
- locked references;
- storyboard/keyframe approval;
- entry/exit continuity;
- object-count and identity constraints;
- QC requirements;
- budget records;
- human approval boundaries.

The provider adapter translates the approved production need. It does not redesign it.

## Phase 3A implementation

The repository implementation lives under:

```text
src/rbl_content_engine/production/
```

It provides:

- prototype-stage enums;
- stable provider capability IDs;
- provider descriptors;
- generation needs;
- cost quotes with explicit units;
- production records;
- a deterministic stability evaluator;
- a provider-commitment authorization guard;
- a read-only provider protocol with cost estimation only.

There is intentionally no generation `submit()` method in Phase 3A.

## Phase 3A acceptance criteria

Phase 3A is complete when:

1. provider support is represented with stable RBL capabilities;
2. provider capability matching is deterministic;
3. cost quotes retain their original units;
4. credits cannot be silently treated as USD;
5. fewer than 5 completed/published videos remain `PROVE_PIPELINE`;
6. 5+ videos with incomplete evidence remain `PROVE_REPEATABILITY`;
7. missing retry/QC/cost/social-observation evidence blocks stabilization;
8. explicit human confirmation is part of the stability gate;
9. recurring-provider commitment fails closed before stabilization;
10. recurring-provider commitment requires explicit human authorization;
11. the production protocol contains no execution/submission method;
12. `make check` and `make test` pass with no network or external side effects.

## Stop condition

After Phase 3A passes its review/test gate, stop before live keyframe generation.

The next production milestone may implement controlled provider discovery and a single human-approved keyframe pilot. It must retain the provider-neutral contract defined here and require a new explicit authorization before any generation spend.
