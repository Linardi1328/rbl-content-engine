# Phase 3D — Repeatability & Publication Observation Loop

## Purpose

Phase 3D tests whether the production process is repeatable across multiple real content items.

RBL still does not publish automatically.

```text
complete approved video
-> human publishes outside RBL
-> MANUAL_EXTERNAL publication receipt
-> first-party observation record
-> production cost/retry/QC record
-> deterministic repeatability evaluation
```

## Publication integrity

A published item exists in RBL only when a human-confirmed `PublicationReceipt` is supplied.

The only supported Phase 3 publication method is:

`MANUAL_EXTERNAL`

The engine must not fabricate a content ID, publication timestamp, or social observation because a video file exists.

A social observation must match an existing publication receipt and platform.

## Repeatability evidence

The default Stage 3A policy requires:

- at least 5 complete + manually published videos;
- retry data for each;
- QC data for each;
- actual cost amount + native unit for each;
- at least 3 published content items with first-party social observations.

This is a process-readiness threshold, not a claim that five posts prove creative success.

## Cost integrity

Provider summaries group cost by provider and native unit. USD, credits, free-generation allowances and local compute remain separate buckets.

## Exit

When the evidence threshold is not met, Stage 3 remains in `PHASE_3D_REPEATABILITY` and reports explicit blockers. It must not advance merely because synthetic/live generation succeeded.
