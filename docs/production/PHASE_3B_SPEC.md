# Phase 3B — Controlled Provider Discovery & Keyframe Pilot

## Purpose

Phase 3B turns the Phase 3A provider-neutral contract into a controlled keyframe workflow.

The durable flow is:

```text
approved SceneCard
+ locked references
+ live provider snapshot
+ native-unit cost quote
+ scoped human generation authorization
-> one keyframe generation
-> RBL QC
-> human approval record
-> locked keyframe identifier
```

Provider discovery is read-only. Record only capabilities, model IDs, constraints, quote units and observed identifiers that the live provider actually returns.

## Live state

Live/account-specific production state belongs under `.production/` and is gitignored. Tracked fixtures must stay synthetic/public-safe.

Recommended live files:

- `.production/provider-snapshots.json`
- `.production/stage3-live.json`

Never commit balances, credentials, cookies, signed upload URLs or private media.

## Keyframe preflight

A keyframe request is READY only when:

- the provider snapshot contains `keyframe_image`;
- every SceneCard reference exists, is human-approved and locked;
- the cost quote belongs to the selected provider;
- the quote retains its native unit;
- the authorization provider and scope match;
- the quote fits the scoped authorization.

Phase 3B does not allow a credit quote to be silently treated as USD.

## Pilot policy

Use one synthetic/public-safe SceneCard for the live pilot. Prefer legitimate free/trial capacity or a low-cost model when available, but never rely on a temporary grant as a permanent architectural assumption.

Successful generation does not imply keyframe approval. Record:

- provider/model;
- observed job/output IDs;
- native-unit cost;
- QC status;
- explicit human approval.

## Exit criteria

Phase 3B implementation is complete when the provider-neutral keyframe preflight and record lifecycle are deterministic and tested. Operationally, Stage 3 may advance to Phase 3C only when at least one keyframe record has `qc_status=PASS` and `human_approved=true`.

No social publication occurs in Phase 3B.
