# Phase 3C — First Complete Video Prototype

## Purpose

Phase 3C proves that an approved keyframe can become one complete controlled video draft without changing the upstream RBL production intent.

```text
approved keyframe
+ SceneCard
+ provider image-to-video capability
+ native-unit quote
+ scoped video authorization
-> 4–8 second draft by default
-> provider task/output record
-> RBL QC
-> human approval
-> complete prototype record
```

## Preconditions

The start keyframe must:

- belong to the same SceneCard;
- have passed QC;
- carry explicit human approval.

The selected provider must expose both `image_to_video` and `start_frame`.

Clips longer than 8 seconds require a non-empty justification.

## Accounting

Every submitted task/retry is part of the production record. Record:

- every observed provider job ID;
- selected model;
- output ID;
- retry count;
- native-unit actual cost;
- duration;
- QC result;
- human approval.

Do not infer cost from a provider credit count unless the provider explicitly supplies a conversion.

## Completion

A video prototype is complete only when QC passes and the video is human-approved.

Completion is not publication. Phase 3C has no social posting tool or automatic publication transition.
