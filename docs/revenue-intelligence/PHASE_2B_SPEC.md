# Phase 2B — Experiment & Historical Baseline Intelligence

## Purpose

Phase 2B is the **final Phase 2 slice** of the RBL Content Engine. Phase 2A decides which opportunities are worth testing and records fixed-window audience/commercial outcomes. Phase 2B adds descriptive comparison against RBL's own historical first-party baseline while retaining treatment metadata.

The durable loop is:

```text
Phase 2A opportunity + hypothesis
-> human-selected treatment metadata
-> manual publication outside the engine
-> fixed-window first-party analytics snapshot
+ mature historical first-party snapshots
-> matched baseline comparison
-> treatment context
-> HUMAN LEARNING / NEXT HYPOTHESIS
```

Phase 2 ends after this capability is reliable. Do not add live APIs, automatic publishing, autonomous optimization, databases, dashboards, paid generation, customer messaging, or causal claims as part of Phase 2.

## Parent and destination

**Parent project:** RBL Content Engine.

**Integration destination:** `src/rbl_content_engine/revenue/`, downstream of Phase 2A and upstream of the next human content decision.

This is not a standalone analytics application.

## Inputs

### Experiment manifest

A local JSON manifest records one or more manually selected content experiments. Each experiment must include:

- unique experiment ID;
- unique published `content_id`;
- platform and format;
- fixed `evaluation_after_days`;
- treatment metadata:
  - topic;
  - hook type;
  - archetype;
  - title variant;
  - thumbnail concept;
  - CTA;
  - monetization routes;
- one or more supported numeric metrics to compare.

Treatment metadata is descriptive. It does not prove why performance changed.

### Current analytics

Reuse the Phase 2A manually exported analytics snapshot contract. Phase 2B requires current content analytics to be at or beyond the experiment's evaluation window before interpreting observed values.

### Historical baseline CSV

The historical dataset is local, manually exported/assembled first-party data. Every row must contain:

- unique `content_id`;
- platform;
- format;
- `published_at` and `observed_at` with timezone offsets;
- `evaluation_after_days`;
- views;
- hook type;
- archetype;
- CTA;
- optional supported numeric metrics.

Every historical row must already be mature for its declared observation window. Duplicate content IDs fail closed.

## Baseline policy

Phase 2B uses one simple deterministic policy:

- cohort keys: `platform + format + evaluation_after_days`;
- exclude the current experiment's own content ID;
- baseline statistic: median;
- minimum usable sample: 3 observations per metric;
- if fewer than 3 metric observations exist, return `INSUFFICIENT_BASELINE` rather than extrapolating.

Do not tune this policy from the small synthetic fixture. A future policy change requires a version change and human review.

## Metric comparison

For each requested metric:

- current observation missing -> `NO_OBSERVATION`;
- baseline sample < 3 -> `INSUFFICIENT_BASELINE`;
- observed > median -> `ABOVE_BASELINE`;
- observed < median -> `BELOW_BASELINE`;
- observed == median -> `AT_BASELINE`.

Also retain numeric delta and observed/baseline ratio when the baseline is non-zero.

These labels are descriptive, not rankings of creative quality and not causal conclusions.

## Treatment context

For `hook_type`, `archetype`, and `cta`, show how many matched historical cohort rows share the same treatment value and expose metric medians only where the same minimum-sample rule is satisfied.

This context is intended to support the next human hypothesis. It must not produce wording such as "this hook caused more views" or "this CTA is the winner."

## Outputs

The Phase 2B CLI generates:

```text
output/
  experiment-baselines.json
  experiment-baselines.md
```

Both artifacts must retain:

- experiment/treatment metadata;
- matched cohort keys and sample size;
- per-metric baseline median/sample/comparison;
- fixed-window timestamps/status;
- treatment-context sample sizes;
- explicit non-causal disclaimer.

## CLI

```bash
PYTHONPATH=src python -m rbl_content_engine.revenue.phase2b \
  examples/revenue-intelligence/experiments.json \
  --analytics examples/revenue-intelligence/analytics.csv \
  --history examples/revenue-intelligence/history.csv \
  --output examples/revenue-intelligence/phase2b-output
```

No network access or secrets are required.

## Required safety behavior

Fail closed on:

- duplicate experiment IDs or content IDs;
- unsupported metrics or monetization routes;
- duplicate historical content IDs;
- malformed or timezone-naive timestamps;
- historical observations earlier than publication;
- historical rows that have not matured to their declared evaluation window;
- current analytics platform mismatching the experiment platform.

Do not use historical performance as factual project evidence.

## Acceptance criteria

Phase 2B is implementation-complete when the synthetic/public-safe fixture can:

1. load two experiments with explicit treatment metadata;
2. match each experiment to the correct platform/format/window baseline cohort;
3. compute deterministic median baselines;
4. enforce a minimum baseline sample;
5. compare multiple audience/commercial metrics;
6. retain hook/archetype/CTA context without causal language;
7. fail closed on invalid history/experiment integrity;
8. generate deterministic JSON/Markdown outputs;
9. remain fully offline and dependency-free;
10. preserve all Phase 2A, ProofLab, Topview, and human-approval boundaries.

## Phase 2 stop condition

Phase 2 is complete after **Phase 2A + Phase 2B** pass the repository's full supported validation matrix and the generated learning artifacts receive human review.

The next phase must be explicitly approved by the human owner. Phase 2 completion does not authorize:

- live platform/account APIs;
- automatic trend research;
- publishing/scheduling;
- autonomous strategy changes;
- paid model/video generation;
- customer/lead messaging;
- databases/dashboards;
- causal attribution claims.
