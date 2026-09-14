# Phase 2A — Revenue & Audience Intelligence Foundation

## Parent and integration destination

**Parent project:** RBL Content Engine.

**Production destination:** the repository's later learning loop, upstream of content planning and human approval. This is not a standalone analytics product and must not become a second content system.

The durable capability is:

```text
dated market / platform snapshot
+ human-scored content opportunity
+ optional manually exported first-party analytics
-> deterministic opportunity ranking
-> explicit monetization routes
-> content hypothesis registry
-> observed performance comparison
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

Phase 2A introduces a third decision domain without collapsing the two existing ones.

### Project evidence

Answers: **what factual claims are allowed?**

Authority remains the local project-evidence / ProofLab path. Revenue or audience data can never upgrade an unsupported project claim.

### Platform research

Answers: **how might the story be packaged for a platform?**

Authority remains a dated local snapshot with source lineage. It is heuristic strategy input, never project evidence.

### Revenue & audience intelligence

Answers: **which content opportunity is commercially worth testing, and what did we observe after publishing?**

Authority is limited to:

- human-scored opportunity factors with explicit lineage;
- manually exported first-party analytics;
- explicit monetization-route tags;
- deterministic comparison against pre-declared hypotheses.

It must not be described as proof of causality or guaranteed future performance.

## Phase 2A inputs

### 1. Opportunity manifest

A JSON file contains one dated research reference and one or more content opportunities.

Minimum shape:

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
      "topic": "How a basketball academy runs a tournament without spreadsheets",
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
        "demand_signal": "Based on the dated local research snapshot.",
        "creator_fit": "Directly supported by an RBL/KHLIM build-in-public workflow."
      },
      "monetization_routes": ["SERVICE_LEAD", "KHLIM_LEAD"],
      "hypothesis": {
        "audience": "grassroots sports operators and builders",
        "hook": "What actually breaks when you run a tournament from spreadsheets?",
        "primary_metric": "watch_time_minutes",
        "target": 1200,
        "direction": "AT_LEAST"
      }
    }
  ]
}
```

Factor scores are integers from 0 to 5. They are explicit human judgments, not model-invented measurements.

### 2. Optional first-party analytics CSV

Phase 2A accepts a manually exported local CSV. It must work without platform credentials.

Required canonical fields:

- `content_id`
- `platform`
- `published_at`
- `views`

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

All numeric metrics must be non-negative. Revenue is observational first-party data, not a guarantee or causal attribution.

### 3. Optional opportunity-to-content mapping

An opportunity may include `content_id` once a human has published a piece of content manually. Before publication, the hypothesis remains `UNOBSERVED`.

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

Persist/display:

- raw factors;
- factor notes;
- scoring version;
- weighted score before risk;
- risk penalty;
- final score;
- deterministic rank.

Ties preserve opportunity input order. Never invent a hidden tie-break.

## Monetization routes

Phase 2A supports explicit route tags only; it does not decide eligibility or execute monetization.

Allowed V1 tags:

- `WATCH_PAGE_ADS`
- `SHORTS_ADS`
- `AFFILIATE`
- `SPONSORSHIP`
- `OWN_PRODUCT`
- `SERVICE_LEAD`
- `KHLIM_LEAD`
- `NONE`

A content opportunity can have multiple routes. Route tags describe the intended commercial path and must not imply guaranteed revenue.

## Hypothesis registry

Every ranked opportunity produces a machine-readable hypothesis record containing at minimum:

- opportunity ID;
- optional content ID;
- topic;
- platform/format;
- audience;
- hook;
- monetization routes;
- primary metric;
- target;
- direction;
- opportunity score and scoring version;
- research snapshot path/date;
- observation status.

Allowed observation states:

- `UNOBSERVED`
- `NO_MATCHING_DATA`
- `TARGET_MET`
- `TARGET_MISSED`

Human publication/approval is external to this module.

## Performance comparison

When matching analytics exist, compare only the declared primary metric to the declared target.

Supported V1 primary metrics are numeric analytics fields from the canonical schema.

- `AT_LEAST`: observed >= target -> `TARGET_MET`
- `AT_MOST`: observed <= target -> `TARGET_MET`
- otherwise -> `TARGET_MISSED`

The learning report may describe an observed result but must not say a hook, format, platform, or monetization route **caused** the result.

If multiple analytics rows share the same `content_id`, aggregate additive metrics by sum. For duration-like metrics, use a deterministic weighted or documented rule; Phase 2A may reject ambiguous multi-row duration aggregation instead of guessing.

## Outputs

Given an opportunity manifest and optional analytics CSV, generate deterministic artifacts such as:

```text
output/
  opportunity-ranking.json
  opportunity-ranking.md
  hypotheses.json
  learning-report.json
  learning-report.md
```

The Markdown files are human review surfaces. JSON is the reusable integration contract.

Every artifact must retain the research snapshot path/date and make clear that scores are decision aids, not forecasts.

## CLI

Target interface:

```bash
PYTHONPATH=src python -m rbl_content_engine.revenue \
  examples/revenue-intelligence/opportunities.json \
  --analytics examples/revenue-intelligence/analytics.csv \
  --output examples/revenue-intelligence/output
```

`--analytics` is optional. The command must require no network access and no secrets.

## Required implementation modules

Keep the implementation small and dependency-free. A reasonable shape is:

```text
src/rbl_content_engine/revenue/
  __init__.py
  models.py
  scoring.py
  analytics.py
  reporting.py
  __main__.py
```

Equivalent smaller organization is acceptable.

## Required tests

At minimum prove:

1. valid factor scores produce the documented deterministic final score;
2. risk reduces the score exactly as documented;
3. invalid factor ranges fail closed;
4. deterministic ranking preserves input order on ties;
5. unknown monetization routes fail closed;
6. research snapshot path/date are retained in all outputs;
7. opportunity analytics never become project evidence;
8. CSV header aliases normalize correctly;
9. extra CSV columns are ignored;
10. missing required CSV fields fail closed;
11. duplicate/ambiguous canonical mappings fail closed;
12. negative metrics fail closed;
13. a matching `content_id` evaluates `AT_LEAST` correctly;
14. `AT_MOST` works correctly;
15. missing content data yields `NO_MATCHING_DATA`;
16. unpublished/unmapped opportunities remain `UNOBSERVED`;
17. output ordering is stable;
18. identical inputs produce byte-for-byte identical generated files;
19. generated reports contain no guaranteed-performance language;
20. no network call, credentials, database, publishing, or external side effect is required.

## Acceptance criteria

Phase 2A is complete when a checked-in synthetic/public-safe example can:

1. rank several content opportunities using the versioned score;
2. show why each score exists;
3. retain monetization-route intent;
4. produce a hypothesis registry before publishing;
5. optionally ingest a manually exported analytics CSV;
6. compare observed performance with the declared hypothesis;
7. produce a concise human learning report;
8. remain fully offline and deterministic;
9. pass `make check` and `make test` on Python 3.11/3.12/3.13;
10. leave Phase 0 factual verification and human approval boundaries intact.

## Integration path

Validated reusable capability should later feed the existing RBL content workflow as:

```text
candidate content ideas
+ dated platform/commercial research
-> Revenue & Audience Intelligence
-> ranked human-reviewed opportunity
-> existing evidence verification + platform treatment pipeline
-> manual publication
-> manually exported first-party analytics
-> Revenue & Audience Intelligence learning report
-> next human decision
```

Do not create a parallel content generator. Reuse the existing content engine's evidence and production boundaries.

## Stop condition

Stop Phase 2A after the offline ranking + hypothesis + analytics-learning loop works reliably on synthetic/public-safe fixtures.

Do **not** add live YouTube/Instagram/TikTok APIs, scheduled trend crawling, automatic publishing, automatic monetization, customer messaging, paid generation, dashboards, databases, or autonomous strategy changes in this milestone.
