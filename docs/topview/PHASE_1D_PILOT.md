# Phase 1D — Controlled Topview Preflight + Reference Pilot

## Purpose

Phase 1D proves that RBL can enter the real Topview production environment safely **without generating video**.

The pilot covers:

```text
live Topview capability discovery
-> non-chargeable preflight
-> account / Canvas access + ownership checks
-> live generation-config inspection only
-> stage 1–2 references
-> record remote asset IDs after external registration
-> human approval
-> cryptographic reference lock
-> stop before storyboard/video generation
```

The operating rule remains:

> RBL decides. Topview renders. QC evaluates. Human approves.

Phase 1D does not authorize image generation, video generation, video editing, timeline operations, export, publishing, or any paid model action.

## Environment limitation

The repository can implement and validate the pilot locally, but `VERIFIED_LIVE` still requires a Codex session where the actual Topview MCP/plugin is installed. A ChatGPT session that cannot see Topview must leave the live pilot blocked rather than synthesizing tool names or remote IDs.

## Required inputs

Read these first:

1. `AGENTS.md`
2. `docs/topview/WORKFLOW.md`
3. `docs/topview/TOOL_MAP.md`
4. `docs/topview/DISCOVERY.md`
5. this file

The pilot consumes:

- a valid Topview Production Manifest;
- `.production/topview-state.json`;
- `.production/topview-capabilities.json` from live discovery;
- `.production/topview-references.json`, created by the reference pilot commands.

All three live `.production/*.json` files remain gitignored.

## Phase 1D hard stops

Stop the pilot when any of these is true:

- Topview MCP/plugin is not connected;
- intended account is not authenticated;
- required Canvas/project cannot be read;
- mutation ownership/permission is not positively verified;
- required live generation configuration cannot be inspected non-chargeably;
- a requested generation capability is not discoverable from the live MCP surface;
- a reference source escapes the workspace root;
- a reference source file cannot be read;
- a locked reference's SHA-256 fingerprint changes;
- a remote asset ID is missing when a reference is being locked;
- human approval is missing;
- any step would require a paid generation.

A failure such as:

```text
Only canvas owner can perform this operation.
```

is a Level 6 production blocker. Do not work around it by changing the creative method.

## Reference authority model

A production reference is not only a filename. RBL binds it to:

```text
RBL reference ID
+ manifest reference type
+ local source path
+ SHA-256 of source bytes
+ remote Topview asset ID
+ explicit human approval
+ lock state
```

Once locked, the source hash is authoritative. If the local file changes later, the pilot reports `REFERENCE_SOURCE_DRIFT` and blocks use until the human explicitly stages and approves a replacement.

This prevents a later Codex session from silently redesigning or swapping an approved reference while keeping the same friendly reference ID.

## Reference lifecycle

### 1. Stage

Select **one or two** manifest references for the Phase 1D pilot.

```bash
PYTHONPATH=src python -m rbl_content_engine.topview reference-init \
  --manifest path/to/topview-production.json \
  --state .production/topview-state.json \
  --registry .production/topview-references.json \
  --workspace-root . \
  --reference REF_PRODUCT \
  --reference REF_STYLE_MASTER
```

Staging:

- verifies the reference exists in the manifest;
- verifies the source is a regular file inside the workspace;
- records its SHA-256 fingerprint;
- creates local reference state;
- does **not** upload or call Topview;
- sets the local production phase to `REFERENCES`.

### 2. Record remote registration

A real Codex + Topview session may use the verified live upload/reference tool outside this local CLI, provided the operation is confirmed non-chargeable and permitted by the workflow.

After Topview returns the exact remote asset ID, record it locally:

```bash
PYTHONPATH=src python -m rbl_content_engine.topview reference-record-remote \
  --state .production/topview-state.json \
  --registry .production/topview-references.json \
  --reference REF_PRODUCT \
  --remote-asset-id <observed-topview-asset-id>
```

Never invent or predict a remote asset ID.

### 3. Human approval

Reference approval is a human/director decision. Codex must not infer approval from successful upload.

```bash
PYTHONPATH=src python -m rbl_content_engine.topview reference-approve \
  --state .production/topview-state.json \
  --registry .production/topview-references.json \
  --reference REF_PRODUCT \
  --human-confirmed
```

Without `--human-confirmed`, approval fails closed.

### 4. Lock

Lock only after remote registration and human approval:

```bash
PYTHONPATH=src python -m rbl_content_engine.topview reference-lock \
  --state .production/topview-state.json \
  --registry .production/topview-references.json \
  --workspace-root . \
  --reference REF_PRODUCT
```

Locking recomputes the file fingerprint. If it no longer matches the staged fingerprint, the operation fails.

### 5. Pilot status

```bash
PYTHONPATH=src python -m rbl_content_engine.topview reference-pilot-status \
  --manifest path/to/topview-production.json \
  --state .production/topview-state.json \
  --capabilities .production/topview-capabilities.json \
  --registry .production/topview-references.json \
  --workspace-root .
```

Possible high-level states:

- `BLOCKED`
- `AWAITING_REMOTE_REGISTRATION`
- `AWAITING_HUMAN_APPROVAL`
- `AWAITING_REFERENCE_LOCK`
- `COMPLETE`

`COMPLETE` means the selected reference pilot succeeded. It does **not** authorize storyboard generation, 720p video generation, or any later paid phase.

## Non-chargeable preflight requirements

Before Phase 1D can become operationally ready, live discovery should positively establish:

- `mcp_connectivity = VERIFIED_LIVE`
- `authentication = VERIFIED_LIVE`
- `canvas_access = VERIFIED_LIVE`
- `canvas_ownership = VERIFIED_LIVE`
- `reference_access = VERIFIED_LIVE`
- `generation_config = VERIFIED_LIVE`
- every generation capability requested by the manifest is present as `VERIFIED_LIVE`
- a live generation-config record exists for each requested generation task type

The generation tools/config are inspected for future compatibility only. Phase 1D must not submit a generation task.

## Exit criteria

Phase 1D is complete when:

1. live discovery is valid and the intended account/Canvas permissions are positively verified;
2. required model/task configuration has been inspected without generation;
3. one or two selected references have real observed remote asset IDs;
4. the human explicitly approves them;
5. the references are locked to unchanged local source fingerprints;
6. local state and registry validate;
7. no generated task exists;
8. actual project spend remains US$0 for the pilot;
9. production stops in the reference phase.

The next phase may prepare storyboards/keyframes, but paid or generative execution requires a separate explicit scope change and human gate.