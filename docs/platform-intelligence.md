# Platform Intelligence — Phase 0

## Why this exists

RBL Content Engine should not create one generic video and resize it for every social platform. The same verified project evidence can support different creative treatments because YouTube, Instagram, and TikTok have different audience behaviors, discovery surfaces, and content norms.

Phase 0 therefore separates two kinds of evidence:

1. **Project evidence** answers: *What are we allowed to say about the project?*
2. **Platform research** answers: *How should we package the verified story for a specific platform and audience?*

Platform research is strategy, not proof of a project claim.

## Phase 0 flow

```text
project evidence
  -> verified claims

manual direction brief + dated platform snapshot
  -> platform-specific content strategy

verified claims + strategy
  -> Content Director
  -> platform-native drafts/storyboards
  -> verifier
  -> PENDING_HUMAN
```

No platform API, web research, analytics ingestion, publishing, or video generation runs inside the Phase 0 pipeline.

## Dated snapshots

Snapshots live under:

```text
research/platforms/YYYY-MM-DD/platforms.json
```

Each snapshot records:

- research date;
- region;
- niche/context;
- audience intent hypotheses;
- current distribution/trend signals;
- recommended content archetypes;
- RBL treatment guidance;
- anti-patterns to avoid;
- source title, publisher, URL, and access date.

The checked-in Phase 0 snapshot is a manually researched input. It should be refreshed manually when strategy is considered stale. The engine must not pretend a snapshot is live data.

## Strategy lineage

Every platform recommendation used by the Content Director should remain traceable to:

- platform;
- format;
- snapshot path/date;
- the relevant source-backed strategy entries.

A generated artifact should make the distinction obvious:

```text
Project fact:
"TaskPebble stores tasks in a local JSON file."
Evidence: examples/taskpebble/evidence.md:L5-L5

Creative strategy:
"Use a problem-first hook on YouTube."
Strategy: research/platforms/2026-08-21/platforms.json
Research date: 2026-08-21
```

The second item can influence presentation, but it cannot validate the first.

## Direction brief

A human supplies a local direction brief such as `examples/taskpebble/direction.json`.

It contains:

- objective;
- audience hypothesis;
- desired voice and creative notes;
- requested platform/format targets;
- human approval state.

The direction brief can be conversational in the future, but Phase 0 uses explicit local JSON so behavior stays deterministic and testable.

## Platform-native outputs

For the same claim set, Phase 0 should be able to create distinct treatments such as:

- **YouTube long-form:** concept/title/hook/outline focused on story depth and sustained value;
- **YouTube Shorts:** self-contained discovery story with an immediate hook and payoff;
- **Instagram Reels:** visually clear, original, share/save-worthy short-form treatment;
- **TikTok:** conversational, curiosity-led, process-oriented short-form treatment.

These are not hard-coded promises about what will go viral. They are dated strategic defaults that a human can override.

## Verification rules

The verifier should check both domains differently.

### Project-claim verification

A factual project statement must be backed by valid project evidence. Unsupported project claims block the result.

### Strategy verification

A strategy recommendation should retain its snapshot/date/source lineage. Missing strategy lineage should be reported, but market strategy itself is not a factual project claim.

The engine must never output language such as:

- "this will go viral";
- "this guarantees more views";
- "the algorithm always favors X";
- fabricated demographic or performance statistics.

If a platform statistic is repeated in a human-facing research artifact, it must be attributable to the dated snapshot source.

## Phase 0 learning boundary

Phase 0 uses only the manually checked-in snapshot and direction brief. It does not learn from the user's accounts yet.

A later phase may ingest approved first-party performance data to compare archetypes against the creator's own baseline, for example hook type, topic, format, retention, shares, saves, and views. That future layer should prefer the creator's observed audience response over generic platform assumptions while preserving human control.
