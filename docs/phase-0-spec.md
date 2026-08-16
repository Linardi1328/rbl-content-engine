# Phase 0 Specification — Manual Evidence-to-Content Pilot

## Purpose

Prove the smallest useful RBL Content Engine workflow before adding automation. Phase 0 is a local/manual pipeline that converts explicit project evidence into a review package while preserving traceability.

## Pipeline

```text
local/project evidence
  -> manually curated claim manifest
  -> deterministic evidence verification
  -> deterministic draft script
  -> verifier report
  -> deterministic storyboard
  -> PENDING_HUMAN
```

“Extracted claims” in Phase 0 means a human or coding agent creates the claim manifest from inspected evidence. Phase 0 does **not** need an LLM to discover claims.

## Technical approach

Use Python 3.11+ and the standard library only unless a dependency is clearly justified in the PR. Plain UTF-8 text/Markdown and JSON are sufficient.

A minimal implementation may use:

```text
src/rbl_content_engine/
  __init__.py
  __main__.py
  pipeline.py

tests/
  test_pipeline.py

examples/taskpebble/
  evidence.md
  claims.json
  output/                 # generated, gitignored
```

Do not create a database, web service, queue, agent framework, vector store, browser automation, social integration, or model integration for Phase 0.

## Evidence model

Evidence is a local UTF-8 file. Claims reference evidence by repository-relative path and 1-based inclusive line range.

Example reference:

```json
{
  "path": "examples/taskpebble/evidence.md",
  "start_line": 5,
  "end_line": 5,
  "quote": "TaskPebble stores tasks in a local JSON file."
}
```

A reference is valid only when:

1. `path` resolves to a regular file inside the repository/workspace root;
2. `start_line` and `end_line` are valid 1-based inclusive bounds;
3. `start_line <= end_line`;
4. `quote` is non-empty; and
5. `quote` occurs verbatim inside the referenced line range.

Do not fetch evidence from the network in the Phase 0 runner. GitHub evidence can be saved/copied into a local evidence file by the human before running the pipeline.

## Claim model

Recommended minimum manifest shape:

```json
{
  "project": "TaskPebble",
  "claims": [
    {
      "id": "claim-001",
      "text": "TaskPebble stores tasks in a local JSON file.",
      "evidence": [
        {
          "path": "examples/taskpebble/evidence.md",
          "start_line": 5,
          "end_line": 5,
          "quote": "TaskPebble stores tasks in a local JSON file."
        }
      ]
    }
  ]
}
```

Claim IDs must be unique and stable. Preserve input order.

A claim is `SUPPORTED` only when it has at least one evidence reference and every attached evidence reference validates. Otherwise it is `UNSUPPORTED`.

If any input claim is unsupported, the overall verification status is `BLOCKED`.

## Draft script

The script is a deterministic short-form draft assembled only from supported claims. It must never silently turn an unsupported claim into prose.

A minimal script format is enough:

- hook/intro that contains no new factual project claims;
- one beat per supported claim, preserving claim order;
- explicit claim ID/evidence references next to each factual beat;
- closing/CTA that contains no unsupported project facts.

If the claim set is blocked, still produce a draft from supported claims if useful, but label the artifact clearly as blocked/not publish-ready.

## Verifier report

The verifier report must be useful to a human reviewer and include:

- overall status: `PASS` or `BLOCKED`;
- each claim ID and text;
- `SUPPORTED` or `UNSUPPORTED` per claim;
- retained evidence references;
- a specific reason for each invalid/unsupported reference;
- a statement that human approval is still required.

`PASS` means every factual input claim is evidence-supported. It does **not** mean approved for publication.

## Storyboard

Generate a simple deterministic storyboard from the draft script. One row/section per script beat is enough, for example:

- beat number;
- voiceover/text;
- source claim ID(s);
- evidence reference(s);
- suggested visual direction that does not assert new facts.

Do not build video generation or editing.

## Approval boundary

Every run ends with:

```text
approval_status: PENDING_HUMAN
```

There is no code path in Phase 0 that changes this to approved or publishes anything.

## Outputs

A successful manual run should write human-readable artifacts under the chosen output directory, preferably:

```text
claims.md
script.md
verifier-report.md
storyboard.md
run.json
```

`run.json` may contain machine-readable statuses and artifact paths. Output ordering/content must be deterministic for identical inputs and workspace contents.

## Required tests

Use `unittest` unless there is a compelling reason not to.

At minimum prove:

1. a supported claim is classified `SUPPORTED`;
2. a claim with no evidence is classified `UNSUPPORTED`;
3. a claim with a bad quote/range is classified `UNSUPPORTED`;
4. unsupported input makes overall status `BLOCKED`;
5. evidence references are retained in reports/script/storyboard where relevant;
6. supported and unsupported claims are distinguishable in the same manifest;
7. identical inputs produce identical generated artifact contents;
8. approval status is always `PENDING_HUMAN`.

Negative tests should mutate the synthetic fixture rather than checking an unsupported claim into the successful demo manifest.

## Phase 0 demo

Use the checked-in `examples/taskpebble/evidence.md` synthetic fixture. Create a successful claim manifest containing only claims literally supported by that evidence.

The end-to-end demo must run locally without network access, secrets, API keys, or paid services.

## Phase 1 — document only, do not implement

A later Phase 1 may automate selected safe preparation steps after the manual pilot is proven, such as:

- reading repository files/commits through an approved GitHub integration;
- proposing candidate claims for human confirmation;
- creating richer script variants from the verified claim set;
- adding structured approval/revision states;
- producing reusable content-package metadata;
- CI checks for evidence traceability.

Phase 1 should still preserve evidence lineage and human approval. Social publishing, customer messaging, video automation, paid model actions, and ProofLab remain separate explicit decisions rather than implicit extensions of Phase 0.
