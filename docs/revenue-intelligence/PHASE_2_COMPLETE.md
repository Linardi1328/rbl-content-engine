# Phase 2 Completion Boundary

Phase 2 of the RBL Content Engine is intentionally limited to two offline, deterministic capabilities.

## Phase 2A — Revenue & Audience Intelligence

Delivered on `main` by PR #18:

- human-scored opportunity ranking with rationale for every factor;
- explicit monetization routes;
- separate audience and commercial hypotheses;
- fixed evaluation windows;
- manually exported cumulative first-party analytics snapshots;
- deterministic target evaluation;
- non-causal learning artifacts.

Authority: `docs/revenue-intelligence/PHASE_2A_SPEC.md`.

## Phase 2B — Experiment & Historical Baseline Intelligence

Implemented on the Phase 2B feature branch:

- explicit treatment metadata for published experiments;
- local first-party historical baseline CSV;
- matched baseline cohorts by platform, format and evaluation window;
- deterministic median baselines;
- minimum sample guardrail;
- per-metric above/below/at-baseline descriptive comparison;
- hook/archetype/CTA historical context;
- deterministic JSON/Markdown report;
- fail-closed integrity rules and non-causal wording.

Authority: `docs/revenue-intelligence/PHASE_2B_SPEC.md`.

## Combined Phase 2 loop

```text
candidate content opportunity
-> Phase 2A ranking + audience/commercial hypothesis
-> HUMAN SELECTS / CREATES CONTENT
-> manual publication outside engine
-> fixed-window first-party snapshot
-> Phase 2A target outcomes
-> Phase 2B matched historical baseline comparison
-> treatment context
-> HUMAN LEARNING / NEXT HYPOTHESIS
```

Phase 2 does not require Phase 0 to be implemented in order to validate its standalone offline learning contracts, but the eventual production integration destination remains the same RBL Content Engine. Once Phase 0 exists, selected Phase 2 opportunities should feed that evidence-to-content workflow rather than a parallel generator.

## Required validation before Phase 2 is accepted

Do not call Phase 2 complete merely because the implementation branch exists. The next step is a dedicated testing/review gate:

1. `make check`;
2. `make test` on Python 3.11, 3.12 and 3.13;
3. Betterleaks/security scan;
4. run the Phase 2A synthetic example and inspect all five generated artifacts;
5. run the Phase 2B synthetic example and inspect JSON/Markdown baseline artifacts;
6. verify deterministic repeat runs;
7. verify Phase 2A target outcomes remain unchanged by Phase 2B;
8. exercise negative cases for duplicate IDs, timestamp/window errors, platform mismatch, insufficient history and unsupported metrics/routes;
9. confirm no live network/API/publishing/payment/generation side effects;
10. human review of the opportunity scoring, target report, baseline cohort selection, sample sizes and non-causal wording.

Only after those checks pass should Phase 2 be marked accepted and the feature branch be merged.

## Phase 2 stop condition

After acceptance, stop Phase 2. Do not silently add:

- live YouTube/Instagram/TikTok analytics APIs;
- scheduled trend crawling;
- automatic publishing;
- autonomous strategy optimization;
- causal attribution;
- paid generation;
- customer/lead messaging;
- dashboards or databases.

Any next phase requires explicit human approval after the Phase 2 test gate.
