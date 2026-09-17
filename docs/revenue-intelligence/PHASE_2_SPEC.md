# Phase 2 — Revenue, Experiment & Audience Learning

## Parent and destination

**Parent project:** RBL Content Engine.

**Production destination:** the repository's offline learning loop around the existing evidence-driven content workflow. Phase 2 is not a second content generator, analytics SaaS, publishing service, or autonomous strategist.

Phase 2 closes this loop:

```text
candidate content ideas
+ dated platform/commercial research
-> Phase 2A opportunity ranking + audience/commercial hypothesis
-> HUMAN SELECTION
-> existing RBL evidence/content workflow
-> manual publication
-> first-party cumulative analytics snapshot
-> Phase 2A fixed-window target evaluation
-> Phase 2B historical experiment ledger + creator baselines
-> Phase 2C planning bridge / next-test context
-> HUMAN DECISION
```

Project evidence remains the authority for factual claims. Platform research remains strategy input. Phase 2 analytics remain observed first-party performance data. None may substitute for another.

## Phase map

### Phase 2A — Revenue & Audience Intelligence

Implemented by `PHASE_2A_SPEC.md`.

Durable capability:

- deterministic opportunity scoring;
- explicit monetization routes;
- required audience target and optional commercial target;
- fixed evaluation horizon;
- one cumulative first-party analytics snapshot per content item;
- separate audience/commercial outcomes;
- deterministic ranking and learning reports.

Phase 2A does not learn a creator baseline and does not change strategy from results.

### Phase 2B — Historical Baseline & Experiment Registry

Adds a local, human-authored registry describing **what was intentionally tested** in historical content.

Each experiment record declares:

- unique experiment ID and content ID;
- platform and format;
- topic tags;
- archetype;
- hook type;
- CTA type;
- fixed evaluation horizon;
- primary variable under test;
- optional controlled comparison group and variant label;
- a human note describing the test intent.

Historical analytics remain manually exported cumulative snapshots using the same strict analytics schema as Phase 2A.

Phase 2B produces:

- an experiment ledger;
- observation maturity status;
- historical cohort baselines grouped by platform, format and evaluation horizon;
- leave-the-current-item-out / prior-history comparisons for historical experiments;
- descriptive controlled comparison groups when explicitly declared.

#### Baseline policy

The creator baseline is descriptive, not predictive.

A cohort key is:

```text
platform + format + evaluation_after_days
```

Only observations whose evaluation horizon has elapsed may enter a baseline. A baseline requires at least **3** eligible observations. Optional metrics may have smaller sample counts and are only emitted when they independently meet the minimum sample requirement.

Use the **median** rather than the mean for the V1 baseline because early creator datasets are small and may contain outliers.

For a historical experiment's own comparison, only earlier published observations in the same cohort may form its prior baseline. The current experiment is never included in the baseline used to describe itself.

Descriptive relations may be `ABOVE_BASELINE`, `AT_BASELINE`, or `BELOW_BASELINE`. These labels are not quality judgments and do not establish causality.

Revenue baselines must never mix currencies. Revenue statistics are emitted separately by observed currency.

#### Derived metrics

When denominators are valid, Phase 2B may derive:

- watch minutes per 1,000 views;
- engagements per 1,000 views (`likes + comments + shares`);
- subscribers gained per 1,000 views;
- clicks per 1,000 views;
- leads per 1,000 views;
- sales per 1,000 views;
- revenue per 1,000 views, separated by currency.

Derived rates are descriptive transformations of observed first-party data, not causal attribution.

### Phase 2C — Learning Ledger & Planning Bridge

Connects Phase 2A candidate opportunities with Phase 2B history without automatically changing the opportunity score.

A current opportunity may declare an optional `experiment_design`:

- topic tags;
- archetype;
- hook type;
- CTA type;
- primary variable intended for the next test.

Phase 2C produces, for each ranked opportunity:

- current opportunity score/rank and monetization intent;
- declared experiment design;
- matching historical cohort size and baseline availability;
- counts of mature history sharing topic, archetype, hook type and CTA type;
- exact-signature history count;
- possible historical reference candidates that match all declared dimensions except the primary test variable;
- deterministic learning notes;
- `decision_status: PENDING_HUMAN`;
- `automatic_score_adjustment: null`.

The engine must never silently update Phase 2A factors from past performance. If a human believes historical results justify a different factor score, the human edits the opportunity manifest and records a new rationale.

## Controlled comparison groups

Historical experiment records may opt into a `comparison_group` and `variant_label`.

A valid group must:

- contain at least two records;
- use one shared `primary_variable`;
- use one platform and evaluation horizon;
- hold all declared design dimensions constant except the primary variable;
- use unique variant labels;
- contain at least two distinct values of the primary variable.

Phase 2 reports the observed metrics for each variant side by side. It does not select a winner or claim that the changed variable caused the difference.

## Data integrity rules

Phase 2 fails closed when:

- experiment IDs or content IDs are duplicated;
- a historical analytics platform conflicts with the experiment registry;
- analytics timestamps are invalid;
- `observed_at < published_at`;
- duplicate analytics rows appear for one content ID;
- a declared comparison group changes more than its one allowed primary variable;
- a revenue statistic would mix currencies;
- an opportunity's experiment design is malformed.

Missing historical analytics do not corrupt the run; the experiment is retained with `NO_MATCHING_DATA` and is excluded from mature baselines.

An observation before its evaluation horizon is `WINDOW_PENDING` and is excluded from mature baselines.

## Inputs

Full Phase 2 uses:

```text
opportunities.json        # Phase 2A opportunity manifest
current-analytics.csv     # optional current opportunity snapshots
experiments.json          # Phase 2B historical experiment registry
history-analytics.csv     # Phase 2B cumulative historical snapshots
```

All inputs are local files. No credentials are required.

## Outputs

The existing Phase 2A outputs remain unchanged in purpose:

```text
opportunity-ranking.json
opportunity-ranking.md
hypotheses.json
learning-report.json
learning-report.md
```

When an experiment registry and historical analytics are supplied, also produce:

```text
experiment-ledger.json
experiment-ledger.md
baseline-report.json
baseline-report.md
planning-bridge.json
planning-bridge.md
phase-2-run.json
```

All JSON output is the reusable contract. Markdown is the human review surface.

`phase-2-run.json` records versions, input paths, counts, baseline minimum sample policy, and `decision_status: PENDING_HUMAN`.

## CLI

Phase 2A remains backward compatible:

```bash
PYTHONPATH=src python -m rbl_content_engine.revenue \
  examples/revenue-intelligence/opportunities.json \
  --analytics examples/revenue-intelligence/analytics.csv \
  --output examples/revenue-intelligence/output
```

Complete Phase 2:

```bash
PYTHONPATH=src python -m rbl_content_engine.revenue \
  examples/revenue-intelligence/opportunities.json \
  --analytics examples/revenue-intelligence/analytics.csv \
  --experiments examples/revenue-intelligence/experiments.json \
  --history-analytics examples/revenue-intelligence/history-analytics.csv \
  --output examples/revenue-intelligence/output
```

`--experiments` and `--history-analytics` are a pair. Supplying only one fails closed.

## Acceptance criteria

Phase 2 is complete when synthetic/public-safe fixtures prove all of the following:

1. Phase 2A behavior remains backward compatible and deterministic.
2. Historical experiment metadata validates strictly.
3. Mature and pending historical observations remain distinguishable.
4. Platform mismatches fail closed.
5. Cohort baselines use only mature observations.
6. V1 baselines use a median and require at least three samples.
7. A historical item never contributes to its own prior baseline.
8. Earlier history only is used for historical prior-baseline comparisons.
9. Derived per-1,000-view metrics handle missing/zero denominators safely.
10. Revenue baseline statistics never mix currencies.
11. Controlled comparison groups reject multi-variable drift.
12. Controlled comparisons remain descriptive and never declare a winner.
13. Planning context never changes Phase 2A scores automatically.
14. Same-topic/archetype/hook/CTA history counts are deterministic.
15. Reference candidates match all dimensions except the declared primary variable.
16. Missing experiment design is visible rather than guessed.
17. Full Phase 2 outputs are byte-for-byte deterministic for identical inputs.
18. Reports retain non-causal / non-forecast disclaimers.
19. `decision_status` remains `PENDING_HUMAN`.
20. No network, credentials, database, publishing, customer messaging, paid model, or external side effect is required.
21. Existing ProofLab, Phase 0 and Topview contract tests remain green.
22. Supported Python 3.11/3.12/3.13 CI remains green.

## Stop condition

Stop Phase 2 after the offline opportunity -> observation -> historical baseline -> planning-context loop works reliably and deterministically.

Do **not** add in Phase 2:

- live YouTube/Instagram/TikTok APIs;
- scheduled research or analytics pulls;
- automatic publishing/scheduling;
- automatic strategy changes or factor rescoring;
- attribution models claiming causality;
- dashboards or databases;
- CRM/customer messaging;
- paid generation;
- autonomous agents.

Those require a later explicit phase and a new human authorization.