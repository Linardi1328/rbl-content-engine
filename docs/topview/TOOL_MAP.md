# RBL Topview Tool Map

## Purpose

This file maps RBL production phases to Topview MCP capabilities.

It is deliberately **not** a hard-coded SDK contract. Topview capabilities and model IDs may change, and the live Codex MCP environment is authoritative for `VERIFIED_LIVE` status.

The current repository does not contain a connected Topview runtime. The entries below are based on Topview's official public `topview-generate` skill/documentation inspected on **2026-09-06** and are therefore marked `OFFICIAL_DOC`, not `VERIFIED_LIVE`.

Official source inspected:

- `https://github.com/topviewai/skill/tree/main/topview-generate`
- `https://github.com/topviewai/skill/blob/main/topview-generate/SKILL.md`
- `https://github.com/topviewai/skill/blob/main/topview-generate/references/video_gen.md`

## Status values

| Status | Meaning |
|---|---|
| `VERIFIED_LIVE` | Tool/schema was discovered in the active Codex Topview MCP session and is currently callable. |
| `OFFICIAL_DOC` | Present in current official Topview documentation but not verified in the active Codex session. |
| `HACKATHON_OBSERVED` | Capability was observed in a previous production session but current name/schema is unknown. |
| `UNVERIFIED` | Expected/desired capability without adequate current evidence. |
| `MANUAL_REQUIRED` | RBL workflow needs the capability but no verified MCP operation is available. |
| `UNAVAILABLE` | Live discovery confirmed the capability is unavailable. |

Do not promote an entry to `VERIFIED_LIVE` based only on this document, memory, or public docs.

## Upstream factual boundary

ProofLab is not a Topview tool and must never be replaced by one. Before factual project content reaches this tool-routing layer, it must pass the local RBL verification contract:

```text
src/rbl_content_engine/prooflab.py
VerifiedClaim
-> require_verified_claims()
-> Topview Production Manifest
-> Topview MCP operations
```

`UNSUPPORTED` or `CONFLICTING` claims stop before Topview. Topview generation, editing, Canvas, or timeline tools may render verified content but cannot supply factual evidence or promote a blocked claim to verified.

## Currently documented Topview MCP surface

| RBL capability | RBL phase | Current documented tool/capability | Status | Chargeable? | Human gate? | Notes |
|---|---|---|---|---|---|---|
| Authenticate | PREFLIGHT | host `mcp_auth` | `OFFICIAL_DOC` | No | As required by host | Authentication is host-managed; do not invent API keys. |
| List boards | PREFLIGHT / CANVAS_SETUP | `topview_list_boards` | `OFFICIAL_DOC` | No | No | Useful for connectivity/account preflight. |
| Create board | CANVAS_SETUP | `topview_create_board` | `OFFICIAL_DOC` | No/unknown | Yes for project setup when creation is desired | Board is not assumed identical to Film Studio Canvas. |
| List board tasks | PREFLIGHT / resume | `topview_list_board_tasks` | `OFFICIAL_DOC` | No | No | Operational history only. |
| Get board task | resume / QC metadata | `topview_get_board_task` | `OFFICIAL_DOC` | No | No | Preserve returned IDs in state. |
| Check credits | PREFLIGHT / budget | `topview_get_credit` | `OFFICIAL_DOC` | No | No | Use before chargeable production when balance matters. |
| Inspect credit logs | budget audit | `topview_list_credit_logs` | `OFFICIAL_DOC` | No | No | Useful for reconciling actual spend. |
| Resolve live model config | PREFLIGHT / generation | `topview_get_generation_config` | `OFFICIAL_DOC` | No | No | **Authoritative source** for model IDs, required fields, supported durations/resolutions and billing hints. |
| Upload credential | REFERENCES / assets | `ta_upload_credential` | `OFFICIAL_DOC` | No/unknown | No | Follow with upload and file verification. |
| Verify uploaded file | REFERENCES / assets | `ta_upload_check_file` | `OFFICIAL_DOC` | No | No | Do not use a file ID before verification succeeds. |
| Generate/edit image | STORYBOARD / KEYFRAMES | `topview_generate_image` | `OFFICIAL_DOC` | Yes | Storyboard gate before motion | `taskType`/model fields must be resolved live. |
| Generate short video | DRAFT_720P / FINAL_1080P | `topview_generate_video` | `OFFICIAL_DOC` | Yes | Required | Public docs describe text-to-video, image-to-video and omni-reference workflows. |
| Prepare Canvas handoff | CANVAS_SETUP / multi-scene | `topview_prepare_canvas_jump` | `OFFICIAL_DOC` | No/unknown | Human interaction follows | Current docs route multi-scene/long finished work toward Canvas. This is a handoff/prefill operation, not proof of direct Canvas editing APIs. |
| Poll task | generation / resume | `topview_query_task` | `OFFICIAL_DOC` | No | No | Poll the same task ID; do not blindly resubmit after timeout. |
| Talking avatar | TIMELINE / AUDIO or specialized shot | `topview_avatar_video` | `OFFICIAL_DOC` | Yes | Required | Use only if the approved treatment needs an avatar. |
| Caption styles | TIMELINE / AUDIO | `topview_list_captions` | `OFFICIAL_DOC` | No | No | Does not imply timeline editing capability. |
| List voices | TIMELINE / AUDIO | `topview_list_voices` | `OFFICIAL_DOC` | No | No | Voice selection remains a creative/human decision where identity matters. |
| Generate voice | TIMELINE / AUDIO | `topview_generate_voice` | `OFFICIAL_DOC` | Yes | Required when chargeable | Must respect approved script. |
| Clone voice | TIMELINE / AUDIO | `topview_clone_voice` | `OFFICIAL_DOC` | Yes | Explicit human authorization required | Do not clone a voice merely because a source recording is available. |
| Generate music | TIMELINE / AUDIO | `topview_generate_music` | `OFFICIAL_DOC` | Yes | Required | Must fit budget and approved creative direction. |
| Generate audio | TIMELINE / AUDIO | `topview_generate_audio` | `OFFICIAL_DOC` | Yes | Required | Live schema/config is authoritative. |
| Remove background | REFERENCES / image prep | `topview_remove_background` | `OFFICIAL_DOC` | Possibly | As applicable | Utility operation only. |
| Product-avatar template discovery | REFERENCES / specialized shot | `topview_list_product_avatar_categories`, `topview_list_product_avatars` | `OFFICIAL_DOC` | No | No | Specialized workflow. |
| Product avatar generation | specialized shot | `topview_product_avatar` | `OFFICIAL_DOC` | Yes | Required | Not a default RBL production route. |

## Publicly documented video input modes

Topview's current public video documentation describes these task concepts. The exact active schema must still be discovered live.

| Input intent | Documented task concept | RBL preference |
|---|---|---|
| text only | `text_to_video` | Use selectively; not the default for important continuity-sensitive shots. |
| approved start frame, optional end frame | `image_to_video` | **Preferred for important RBL shots after storyboard approval.** |
| several references | multi-image image-to-video or `omni_reference` | Use only when composition can remain controlled. |
| named image/video references | `omni_reference` | Specialist route; do not substitute for an approved keyframe when composition matters. |
| motion control | `motion_control` where live schema exposes it | Specialist route. |
| source avatar video | `video_avatar` | Specialized talking-head workflow. |

## RBL defaults for generation

These are RBL workflow rules, not claims about permanent Topview limits:

- Prefer approved-keyframe `image_to_video` for important shots.
- Default controlled generated clip length: **4–8 seconds**.
- Use 720p for draft motion/composition tests when supported.
- Generate/finalize at 1080p only after required QC and human approval.
- Never assume a historical model ID such as a particular Seedance version is still the correct submit value.
- Resolve `submitModel`, required parameters, supported duration and resolution from live generation config before any chargeable call.
- Preserve task IDs immediately and poll existing tasks rather than resubmitting on timeout.

## Capabilities observed during the RBL hackathon but requiring live rediscovery

These are production capabilities the team observed/used previously. The current direct MCP tool names and schemas are intentionally **not** guessed here.

| Desired capability | Phase | Status | Required before automation? |
|---|---|---|---|
| Direct Canvas creation/listing/state beyond board helpers | PREFLIGHT / CANVAS_SETUP | `HACKATHON_OBSERVED` | Yes |
| Asset/media/text/group node operations | REFERENCES / environments | `HACKATHON_OBSERVED` | Yes |
| SceneCard creation/manipulation | SCENECARDS | `HACKATHON_OBSERVED` | Yes |
| Storyboard/keyframe node workflow | STORYBOARD / KEYFRAMES | `HACKATHON_OBSERVED` | Yes |
| Targeted `video_edit` | TARGETED EDIT | `HACKATHON_OBSERVED` | Yes |
| Timeline editing | TIMELINE / AUDIO | `HACKATHON_OBSERVED` | Yes |
| Timeline export | EXPORT | `HACKATHON_OBSERVED` | Yes |
| Canvas ownership/permission inspection | PREFLIGHT | `UNVERIFIED` | **Critical** |

Until live discovery verifies an operation, Codex must either use a verified alternative or mark the step `MANUAL_REQUIRED`.

## Live discovery procedure for Codex

Before the first Topview production operation in a Codex session:

1. Confirm the intended Topview MCP/plugin is installed and connected.
2. Enumerate its currently exposed Topview tools and read their schemas.
3. Record the MCP/plugin/skill version when available.
4. Compare live tools against this file.
5. Mark each required capability `VERIFIED_LIVE`, `MANUAL_REQUIRED`, or `UNAVAILABLE` for the current session.
6. Verify authentication using a non-chargeable read operation.
7. Verify intended Canvas/project access using non-chargeable operations where possible.
8. Verify ownership/permission for planned mutation operations **before** paid generation. If the MCP provides no safe ownership check, require an explicit manual preflight confirmation rather than probing with a chargeable action.
9. Call the live generation-config tool for every generation task type that will be used.
10. Record available model submit IDs, required fields, supported resolutions/durations and billing hints into local production state.
11. Confirm the projected production cost remains under the RBL configured budget.
12. Only then request the applicable human generation gate.

## Error rules

### Authentication / permission

If any tool returns an authentication, Canvas ownership, or permission error:

```text
STOP
-> preserve current state
-> classify as recovery Level 6
-> resolve auth/ownership
-> repeat preflight
```

Do not switch creative methods to work around permissions.

### Missing tool

If a workflow step references a capability not present in live discovery:

```text
mark MANUAL_REQUIRED or UNAVAILABLE
-> do not invent a tool name
-> do not make raw undocumented API calls
-> report the gap before the stage is needed
```

### Unsupported model or parameter

Re-read live generation configuration. Do not silently switch to a different paid model without the applicable human approval and budget check.

## Future maintenance

When a live Codex/Topview session is available, update this document with:

- `last_verified_live` date;
- MCP/plugin/skill version;
- exact verified tool names;
- relevant schema notes;
- permission/ownership preflight method;
- timeline/export capability status;
- targeted video-edit capability status.

Do not delete historical observations merely because a capability temporarily disappears; change its status and record the verified date.
