# Phase 2A — Revenue & Audience Intelligence Foundation

## Parent and integration destination

**Parent project:** RBL Content Engine.

**Production destination:** the repository's later learning loop, upstream of content planning and human approval. This is not a standalone analytics product and must not become a second content system.

The durable capability is:

```text
dated market / platform snapshot
+ human-scored content opportunity
+ optional manually exported first-party analytics snapshot
-> deterministic opportunity ranking
-> explicit monetization routes
-> audience + commercial hypothesis registry
-> fixed-window observed performance comparison
-> human-readable learning report
-> HUMAN DECISION
```

The purpose is to help RBL decide **what to make next and why**, while preserving the existing factual-evidence boundary.

## Non-goals

Phase 2A does **not**:

- browse the web or perform live trend research;
- connect to YouTube, Instagram, TikTok, ad, affiliate, commerce, CRM, or payment APIs;
- publish or schedule content;
- message customers or leads;
- spend money or call paid models;
- claim causal attribution from observational performance data;
- replace human approval;
- use market or analytics data as evidence for factual project claims;
- change the existing ProofLab boundary;
- require a database, web server, queue, vector store, or agent framework.

## Evidence domains remain separate

### Project evidence

Answers: **what factual claims are allowed?** Revenue or audience data can never upgrade an unsupported project claim.

### Platform research

Answers: **how might the story be packaged for a platform?** Authority remains a dated local snapshot with source lineage. It is heuristic strategy input, never project evidence.

### Revenue & audience intelligence

Answers: **which content opportunity is commercially worth testing, and what did we observe after publishing?** Authority is limited to human-scored factors, manually exported first-party analytics, explicit monetization-route intent, and deterministic comparison against pre-declared targets.

It must not be described as proof of causality or guaranteed future performance.

## Phase 2A inputs

### 1. Opportunity manifest

A JSON file contains one dated research reference and one or more content opportunities.

Each opportunity contains:

- unique opportunity ID;
- optional `content_id`, unique across the manifest once assigned;
- topic, platform and format;
- all seven 0–5 scoring factors;
- a non-empty rationale for **every** scoring factor, including risk;
- one or more explicit monetization routes;
- a fixed observation horizon in days;
- one required audience target;
- zero or one commercial target.

Example:

```json
{
  "version": "RBL_REVENUE_INTELLIGENCE_V1",
  "research_snapshot": {
    "path": "research/platforms/2026-08-21/platforms.json",
    "research_date": "2026-08-21"
  },
  "opportunities": [
    {
      "id": "opp-001",
      "content_id": "yt-001",
      "topic": "How a basketball tournament moves beyond spreadsheets",
      "platform": "youtube",
      "format": "long_form",
      "factors": {
        "demand_signal": 4,
        "creator_fit": 5,
        "originality": 5,
        "production_efficiency": 4,
        "evergreen_value": 4,
        "monetization_fit": 5,
        "risk": 1
      },
      "factor_notes": {
        "demand_signal": "Human judgment grounded in the dated local research snapshot.",
        "creator_fit": "Direct fit with an RBL build-in-public workflow.",
        "originality": "Sports operations plus software implementation.",
        "production_efficiency": "Can use existing UI footage and diagrams.",
        "evergreen_value": "The operator problem recurs across tournaments.",
        "monetization_fit": "Can feed service and KHLIM interest.",
        "risk": "Low when all factual claims remain evidence-backed."
      },
      "monetization_routes": ["SERVICE_LEAD", "KHLIM_LEAD"],
      "hypothesis": {
        "audience": "grassroots sports operators and builders",
        "hook": "What actually breaks when you run a tournament from spreadsheets?",
        "evaluation_after_days": 7,
        "audience_target": {
          "metric": "watch_time_minutes",
          "target": 1200,
          "direction": "AT_LEAST"
        },
        "commercial_target": {
          "metric": "leads",
          "target": 5,
          "direction": "AT_LEAST"
        }
      }
    }
  ]
}
```

Factor scores are explicit human judgments, not model-invented measurements. Requiring a rationale for every factor makes later rescoring auditable instead of hiding subjective changes.

### 2. Audience and commercial targets

The required audience target may use:

- `views`
- `impressions`
- `watch_time_minutes`
- `average_view_duration_seconds`
- `likes`
- `comments`
- `shares`
- `subscribers_gained`

The optional commercial target may use:

- `clicks`
- `leads`
- `sales`
- `revenue`

Every target specifies `AT_LEAST` or `AT_MOST` and a non-negative numeric target.

A `revenue` target must also specify `currency`. Observed revenue with a missing or different currency fails closed instead of being compared as if currencies were interchangeable.

### 3. Fixed evaluation horizon

Every hypothesis declares `evaluation_after_days` from 0 to 365.

The system does not grade a target before:

```text
published_at + evaluation_after_days
```

If the analytics snapshot is earlier than that point, observation status is `WINDOW_PENDING` and both target outcomes remain pending even if current values already cross the target.

This prevents a 24-hour observation and a 30-day observation from being treated as equivalent experiments.

### 4. Optional first-party analytics CSV

Phase 2A accepts a manually exported local cumulative snapshot. It must work without platform credentials.

Required canonical fields:

- `content_id`
- `platform`
- `published_at`
- `observed_at`
- `views`

`published_at` and `observed_at` must be ISO datetimes with timezone offsets. `observed_at` cannot precede `published_at`.

Optional canonical fields:

- `impressions`
- `watch_time_minutes`
- `average_view_duration_seconds`
- `likes`
- `comments`
- `shares`
- `subscribers_gained`
- `revenue`
- `currency`
- `clicks`
- `leads`
- `sales`

Common harmless header aliases may map deterministically to canonical fields. Extra columns are ignored. Ambiguous duplicate mappings or missing required columns fail closed.

Phase 2A accepts **one cumulative analytics row per `content_id`**. Duplicate rows fail closed. It does not guess whether duplicate exports are cumulative snapshots, overlapping periods, or disjoint segments, because summing the wrong shape can silently double-count performance.

All numeric metrics must be non-negative.

## Opportunity scoring

Use one fixed, versioned deterministic policy in Phase 2A.

Positive weighted score:

- demand signal: 20%
- creator fit: 20%
- originality: 15%
- production efficiency: 10%
- evergreen value: 10%
- monetization fit: 25%

Each factor is 0–5. Convert the weighted average to a 0–100 score.

Risk is a separate 0–5 penalty:

```text
final_score = clamp(weighted_positive_score - (risk * 4), 0, 100)
```

Persist/display raw factors, factor rationales, scoring version, weighted score before risk, risk penalty, final score and deterministic rank. Ties preserve opportunity input order. Never invent a hidden tie-break.

Do not tune weights from a handful of observations. A later scoring version requires deliberate human review and a version change.

## Monetization routes

Allowed V1 tags:

- `WATCH_PAGE_ADS`
- `SHORTS_ADS`
- `AFFILIATE`
- `SPONSORSHIP`
- `OWN_PRODUCT`
- `SERVICE_LEAD`
- `KHLIM_LEAD`
- `NONE`

Route tags describe intended commercial paths only. They do not establish platform eligibility, attribution, or guaranteed revenue.

## Observation contract

The top-level observation state is one of:

- `UNOBSERVED` — no `content_id` has been assigned;
- `NO_MATCHING_DATA` — content exists in the manifest but no analytics snapshot matches;
- `WINDOW_PENDING` — matching analytics exist, but the declared evaluation horizon has not elapsed;
- `EVALUATED` — the observation horizon has elapsed and declared targets may be graded.

Each audience/commercial target then has its own status:

- `UNOBSERVED`
- `NO_MATCHING_DATA`
- `WINDOW_PENDING`
- `TARGET_MET`
- `TARGET_MISSED`

This prevents an audience result from being mistaken for a commercial result. A Short can miss a view target while still meeting a lead target, or vice versa.

When matching analytics exist:

1. `content_id` must match;
2. analytics platform must match the opportunity platform, case-insensitively;
3. the observation window must have elapsed before grading;
4. each declared target compares only its own metric;
5. revenue currency must match exactly, case-insensitively.

The learning report may describe observations but must never say the hook, format, platform, or monetization route **caused** them.

## Outputs

Generate deterministic artifacts:

```text
output/
  opportunity-ranking.json
  opportunity-ranking.md
  hypotheses.json
  learning-report.json
  learning-report.md
```

The Markdown files are human review surfaces. JSON is the reusable integration contract.

Every artifact retains research snapshot path/date and states that scores/observations are decision aids rather than forecasts or causal proof.

The learning artifacts retain:

- opportunity score/version;
- audience and hook;
- monetization-route intent;
- evaluation horizon;
- published, observed and evaluation-due timestamps when analytics match;
- separate audience target/outcome;
- separate commercial target/outcome;
- observed metrics snapshot.

## CLI

```bash
PYTHONPATH=src python -m rbl_content_engine.revenue \
  examples/revenue-intelligence/opportunities.json \
  --analytics examples/revenue-intelligence/analytics.csv \
  --output examples/revenue-intelligence/output
```

`--analytics` is optional. The command requires no network access and no secrets.

## Required tests

At minimum prove:

1. documented scoring and risk penalty are exact;
2. invalid factor ranges fail closed;
3. every factor requires a rationale;
4. deterministic ranking preserves input order on ties;
5. unknown monetization routes fail closed;
6. assigned content IDs are unique across opportunities;
7. research snapshot path/date remain in outputs;
8. CSV aliases normalize and irrelevant columns are ignored;
9. required timestamp/metric fields are enforced;
10. timestamps require timezone offsets and `observed_at >= published_at`;
11. duplicate canonical column mappings fail closed;
12. negative metrics fail closed;
13. duplicate content rows fail closed instead of being summed;
14. platform mismatch fails closed;
15. the evaluation horizon produces `WINDOW_PENDING` before grading;
16. audience and commercial targets can produce different outcomes;
17. missing target metrics yield target-level `NO_MATCHING_DATA`;
18. `AT_MOST` works correctly;
19. revenue targets require currency and mismatches fail closed;
20. unpublished/unmapped opportunities remain `UNOBSERVED`;
21. identical inputs produce byte-for-byte identical artifacts;
22. reports contain no guaranteed-performance or causal language;
23. no network call, credentials, database, publishing, or external side effect is required.

## Acceptance criteria

Phase 2A is complete when a checked-in synthetic/public-safe example can:

1. rank several content opportunities using the versioned score;
2. show why every factor score exists;
3. retain monetization-route intent;
4. produce separate audience/commercial hypotheses before publishing;
5. define a fixed observation horizon;
6. optionally ingest one cumulative first-party analytics snapshot per content item;
7. compare mature observations with both declared targets;
8. distinguish audience success from commercial success;
9. remain fully offline and deterministic;
10. pass `make check` and `make test` on Python 3.11/3.12/3.13;
11. leave Phase 0 factual verification and human approval boundaries intact.

## Integration path

```text
candidate content ideas
+ dated platform/commercial research
-> Revenue & Audience Intelligence
-> ranked human-reviewed opportunity
-> existing evidence verification + platform treatment pipeline
-> manual publication
-> manually exported first-party analytics snapshot
-> fixed-window Revenue & Audience learning report
-> next human decision
```

Do not create a parallel content generator. Reuse the existing content engine's evidence and production boundaries.

## Stop condition

Stop Phase 2A after the offline ranking + dual-target hypothesis + fixed-window analytics-learning loop works reliably on synthetic/public-safe fixtures.

Do **not** add live YouTube/Instagram/TikTok APIs, scheduled trend crawling, automatic publishing, automatic monetization, customer messaging, paid generation, dashboards, databases, or autonomous strategy changes in this milestone.
