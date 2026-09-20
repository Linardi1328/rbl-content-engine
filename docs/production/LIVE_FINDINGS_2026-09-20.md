# Stage 3 Live Provider Findings — 2026-09-20

This file records safe, non-secret capability findings observed during the Stage 3 implementation session. Account-specific balances, job IDs, output URLs, credentials and signed URLs remain outside tracked repository state.

## Higgsfield plugin

Observed read-only surface:

- live model catalog;
- per-model parameter/media-role inspection;
- image/video cost estimation in Higgsfield credits;
- balance/plan readback;
- generation submission;
- task polling.

Observed account-tier behavior:

- `z_image` was executable for a synthetic 9:16 keyframe on the current free workspace;
- a reference-based `nano_banana` submission was rejected before job creation with `Requires basic plan or higher`;
- `seedance_2_0_mini` image-to-video was rejected before job creation with the same plan requirement;
- `kling3_0_turbo` image-to-video was rejected before job creation with the same plan requirement;
- cost estimation can succeed even when live execution is blocked by account tier.

## Architectural consequence

RBL must keep three concepts separate:

```text
model discovered
!= cost estimable
!= executable for the active account/workspace
```

A provider snapshot therefore records discovered model IDs separately from model-level executable/blocked status. Production preflight fails closed when the selected model has not been positively observed as executable.

A failed pre-submission tier check records no generation task and no inferred spend.

## Scope

These findings are dated observations, not timeless provider guarantees. Re-discover the live surface before later production runs.
