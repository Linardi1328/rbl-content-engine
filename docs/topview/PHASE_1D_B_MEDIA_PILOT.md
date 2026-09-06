# Phase 1D-B — Real Media Reference Verification

## Purpose

Phase 1D-A proved the control-plane lifecycle with metadata-only `.txt` reference cards. Phase 1D-B proves the missing media-path claim:

```text
real PNG/JPEG bytes
-> local format + SHA-256 inspection
-> live non-chargeable Topview media registration/upload
-> observed remote reference identifier
-> live read/inspection proves remote object is image/media-backed
-> human approval
-> cryptographic lock
-> stop before generation
```

Phase 1D-B is complete only when the remote Topview object is positively verified as media/image-backed. A generic Canvas node or metadata card alone is **not** sufficient.

## Scope

Use exactly one safe image reference for the pilot:

- `REF_MEDIA`
- `examples/topview/reference-pilot/ref-media.png`
- `examples/topview/reference-pilot/media-manifest.json`

The checked-in PNG is synthetic and contains no personal or project-sensitive data.

No image generation, video generation, Seedance generation, targeted edit, timeline mutation, export, publishing, or other paid model action is authorized.

## Required reading

1. `AGENTS.md`
2. `docs/topview/WORKFLOW.md`
3. `docs/topview/TOOL_MAP.md`
4. `docs/topview/DISCOVERY.md`
5. `docs/topview/PHASE_1D_PILOT.md`
6. this file

## Step 1 — Inspect local media bytes

Run:

```bash
PYTHONPATH=src python3 -m rbl_content_engine.topview.media_cli \
  --workspace-root . \
  --path examples/topview/reference-pilot/ref-media.png
```

The expected tracked fixture properties are:

- format: `PNG`
- MIME: `image/png`
- width: `256`
- height: `256`
- SHA-256: `a3df5b95c9b469a04b0a11359fe8149858d9524ffe2eb96484e6dc11c0862af1`

Do not continue if the local inspector fails or the hash differs.

## Step 2 — Reuse/reconfirm live discovery

Use the current live Topview MCP/plugin surface as authoritative. Revalidate `.production/topview-capabilities.json` if it is still from the same authenticated environment; otherwise repeat live discovery.

The pilot requires non-chargeable access to:

- MCP connectivity;
- authentication;
- Canvas/project access;
- Canvas ownership/writer permission;
- reference/media registration or upload capability;
- a non-chargeable way to read or inspect the returned remote object.

Do not infer media support from a tool name alone.

## Step 3 — Technical preflight

Use `media-manifest.json` with local Phase 1D preflight/state. Preflight may inspect future `image_to_video` configuration but must not submit generation.

The state must still enforce:

```text
paid_generation_authorized = false
generated_tasks_allowed = false
generated_tasks = []
actual_project_spend_usd = 0
```

If a fresh preflight reaches `READY_FOR_CONFIRMATION`, stop for explicit human confirmation.

## Step 4 — Stage REF_MEDIA locally

Initialize a fresh reference registry for `REF_MEDIA` using the existing Phase 1D reference tooling.

The registry fingerprint must equal the local media inspector SHA-256.

## Step 5 — Register/upload through live Topview

Use only the exact live Topview MCP operation observed for real media/reference registration.

Requirements:

- send the actual PNG/media file, not a text description of its path;
- do not use a metadata-only asset-card route if a true media upload/reference route exists;
- record only the identifier actually returned live;
- do not infer approval from successful upload;
- do not generate anything to test the reference.

If the tool cannot accept real media bytes/file references without generation, mark Phase 1D-B `BLOCKED` rather than falling back to the Phase 1D-A metadata-card behavior.

## Step 6 — Prove remote media semantics

Before human approval, perform a non-chargeable read/inspection of the returned remote object.

At least one live response must positively establish image/media semantics, for example through observed fields such as:

- node/asset type = image/media;
- MIME/media type = image;
- image dimensions;
- file/media URL or media metadata;
- attachment/media payload metadata.

The exact field names are determined by the live MCP schema. Do not invent them.

A returned Canvas `nodeId` is acceptable as the remote identifier **only if** the subsequent live read proves that node is media/image-backed.

## Step 7 — Human approval and lock

Stop at the human reference-approval gate and report:

1. RBL reference ID;
2. local media path;
3. local format/MIME/dimensions;
4. SHA-256;
5. exact observed remote identifier;
6. live evidence that the remote object is media/image-backed;
7. generated task count;
8. actual spend;
9. warnings/capability limits.

Only after explicit human approval may Codex run the existing `reference-approve` and `reference-lock` commands.

Locking must recompute the local SHA-256 and fail on drift.

## Exit criteria

Phase 1D-B is `COMPLETE` only if all are true:

```text
local source = valid PNG/JPEG
local SHA-256 = stable
live Topview registration = succeeded
remote identifier = observed, not inferred
remote object = positively verified as image/media-backed
human approval = explicit
reference lock = complete
source drift = none
generated tasks = 0
actual spend = US$0
```

Then stop. Phase 1D-B does **not** authorize storyboard/keyframe generation or any paid production call.
