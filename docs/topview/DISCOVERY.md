# RBL Topview Live Discovery

## Purpose

Phase 1B turns Topview capability discovery into an explicit, resumable production step. The goal is to prevent Codex from confusing "an MCP tool exists" with "RBL knows how and when to use it".

This document does **not** authorize paid generation. It defines how a Codex session with the actual Topview MCP/plugin installed should discover and record the live tool surface before production.

The live environment is authoritative for `VERIFIED_LIVE`. Public documentation and prior hackathon experience are useful references only.

## Required reading

Before discovery, read:

1. `AGENTS.md`
2. `docs/topview/WORKFLOW.md`
3. `docs/topview/TOOL_MAP.md`
4. this file

## Discovery output

A real Codex + Topview session should write its local discovery result to:

```text
.production/topview-capabilities.json
```

That file is mutable execution metadata and must remain gitignored. The tracked design contract is:

```text
schemas/topview-capabilities.schema.json
.production/topview-capabilities.example.json
```

Do not commit live account identifiers, Canvas IDs, remote asset IDs, task IDs, or capability data that may expose private production state.

## Discovery rules

- Discovery must use the actual installed MCP/plugin surface.
- Never promote a capability to `VERIFIED_LIVE` from memory, public docs, or `TOOL_MAP.md` alone.
- Never invent a tool name to make the workflow appear complete.
- Do not execute a paid generation merely to prove a tool exists.
- Prefer non-chargeable read/config operations for connectivity, authentication, account, Canvas, credit, and model checks.
- If ownership/permission cannot be checked safely, record it as `MANUAL_REQUIRED` or `UNVERIFIED` and block chargeable production.
- Model IDs, required fields, supported duration, resolution, native-audio support, and billing hints must come from live configuration when available.
- Tool/schema discovery is not creative approval. Human gates remain separate.

## Canonical capability IDs

Use these stable RBL capability IDs even if Topview tool names change:

| Capability ID | Meaning | Hard requirement? |
|---|---|---|
| `mcp_connectivity` | Topview MCP/plugin responds | Yes |
| `authentication` | intended account is authenticated | Yes |
| `canvas_access` | intended Canvas/project is accessible | Yes when Canvas is used |
| `canvas_ownership` | mutation permissions/ownership are sufficient | Yes before chargeable Canvas mutations |
| `reference_access` | required approved references can be accessed | Yes when references are required |
| `generation_config` | live model/task configuration can be read | Yes before chargeable generation |
| `image_generation` | storyboard/keyframe image generation | Only when required by manifest |
| `text_to_video` | text-to-video generation | Only when required by manifest |
| `image_to_video` | approved-keyframe image-to-video | Only when required by manifest |
| `omni_reference` | named/multi-reference generation | Only when required by manifest |
| `motion_control` | motion-control workflow | Only when required by manifest |
| `task_monitoring` | generation task/status polling | Yes for async generation |
| `targeted_video_edit` | localized repair of an existing video | Optional; may become `MANUAL_REQUIRED` |
| `timeline_edit` | timeline assembly/editing | Optional if manual assembly is accepted |
| `timeline_export` | export from Topview timeline/Canvas | Optional if manual export is accepted |

A capability can be present in `TOOL_MAP.md` as `OFFICIAL_DOC` or `HACKATHON_OBSERVED` while still being `UNVERIFIED` in the current live discovery snapshot.

## Live discovery procedure

### 1. Confirm connection

Enumerate the installed tools/skills/connectors and confirm the Topview MCP/plugin is present. Record the MCP/plugin name and version if the environment exposes them.

If no Topview integration is present:

```text
session.status = BLOCKED
mcp_connectivity = UNAVAILABLE
```

Stop discovery. Do not synthesize the missing surface from public documentation.

### 2. Confirm authentication

Use a non-chargeable read operation where possible. Record only a minimal non-secret account hint if useful. Never store tokens, cookies, credentials, or `.env` contents.

### 3. Enumerate tool schemas

For each required RBL capability:

- identify the exact live tool name;
- inspect the current input/output schema;
- record whether the capability is `VERIFIED_LIVE`, `MANUAL_REQUIRED`, `UNAVAILABLE`, or still `UNVERIFIED`;
- record whether the operation appears chargeable;
- record concise schema notes needed by the operator.

Discovery should verify the existence/schema of chargeable generation tools without submitting a generation.

### 4. Verify Canvas/project access

Use safe read operations when possible. Record access separately from ownership/mutation permission.

If the environment cannot safely prove ownership/mutation permission, do not infer it from read access.

Known hard-stop class:

```text
Only canvas owner can perform this operation.
```

### 5. Resolve live generation configuration

Before any generation phase, read live configuration for each required task type. Record:

- task type;
- resolved submit model IDs;
- supported resolutions;
- supported durations;
- required fields;
- native-audio capability when exposed;
- billing/cost hints when exposed.

Do not persist a historical model name as though it were permanently valid.

### 6. Save the capability snapshot

Write `.production/topview-capabilities.json`, then run the local validator:

```bash
PYTHONPATH=src python -m rbl_content_engine.topview validate-capabilities \
  .production/topview-capabilities.json
```

### 7. Run local preflight evaluation

With a production manifest and state file available:

```bash
PYTHONPATH=src python -m rbl_content_engine.topview preflight \
  --manifest path/to/topview-production.json \
  --state .production/topview-state.json \
  --capabilities .production/topview-capabilities.json
```

During Phase 1, this command remains fail-closed for chargeable production. A later explicitly authorized phase may add a separate human-controlled mechanism that permits paid execution.

## Status semantics

`VERIFIED_LIVE` means the current Codex session actually observed the tool/schema needed for the capability.

`MANUAL_REQUIRED` means the RBL workflow can continue only with an explicit manual step; it is not equivalent to an automated capability.

`UNAVAILABLE` means live discovery confirmed the current environment cannot perform the capability.

`UNVERIFIED` means discovery has not established the capability one way or the other.

## Current ChatGPT-session result

As of 2026-09-06, this ChatGPT environment does not expose a connected Topview MCP/plugin. Plugin discovery did not return Topview. Therefore no capability is promoted to `VERIFIED_LIVE` from this session.

This is expected to be completed from the actual Codex environment where Topview is installed.
