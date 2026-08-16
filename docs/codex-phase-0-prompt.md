# Codex Prompt — Implement RBL Content Engine Phase 0

Use this prompt with Codex from the repository root.

---

You are implementing **Phase 0 of the RBL Content Engine** in this repository.

Before changing code, read these files in full:

1. `AGENTS.md`
2. `docs/phase-0-spec.md`
3. `README.md`
4. `examples/taskpebble/evidence.md`
5. `examples/taskpebble/claims.json`

Treat `AGENTS.md` and `docs/phase-0-spec.md` as authoritative. Do not expand scope beyond them.

## Goal

Implement the smallest evidence-driven manual content pilot:

```text
local/project evidence
-> claim manifest with evidence references
-> deterministic claim verification
-> deterministic draft short-form script
-> verifier report
-> deterministic storyboard
-> PENDING_HUMAN
```

This is a manual pilot. Do **not** automate publishing, customer messaging, video creation, paid APIs/models, GitHub ingestion, or ProofLab.

## Required implementation

Build a small Python 3.11+ standard-library-only package under `src/rbl_content_engine/`.

Prefer a compact structure such as:

```text
src/rbl_content_engine/
  __init__.py
  __main__.py
  pipeline.py
```

Add more modules only if they clearly improve readability. Do not create frameworks, services, databases, agents, queues, vector stores, or network clients.

### CLI

Provide this local command:

```bash
PYTHONPATH=src python -m rbl_content_engine examples/taskpebble/claims.json --output examples/taskpebble/output
```

The command must require no network access and no secrets.

It must generate these human-readable files in the output directory:

```text
claims.md
script.md
verifier-report.md
storyboard.md
run.json
```

For identical inputs and workspace contents, generated file contents must be deterministic.

### Evidence verification

Implement the evidence/reference rules exactly as specified in `docs/phase-0-spec.md`.

At minimum validate:

- evidence path is repository/workspace-local and resolves to a regular file;
- line numbers are 1-based inclusive integers;
- line bounds exist and `start_line <= end_line`;
- quote is non-empty;
- quote occurs verbatim within the referenced line range.

Prevent path traversal outside the workspace root.

A claim is `SUPPORTED` only if it has at least one evidence reference and all attached references validate. Otherwise it is `UNSUPPORTED`.

If any claim is unsupported, overall verification is `BLOCKED`.

Do not silently repair or reinterpret evidence references.

### Claim/evidence output

`claims.md` must preserve, for every claim:

- claim ID;
- claim text;
- support status;
- evidence path;
- line range;
- quote;
- failure reason when unsupported.

### Draft script

Generate a simple deterministic short-form script using **supported claims only**.

Requirements:

- no newly invented factual project claims;
- preserve supported claim order;
- each factual beat retains its source claim ID and evidence reference(s);
- hook and closing may be generic but must not introduce project facts;
- if overall verification is `BLOCKED`, visibly mark the script as blocked/not publish-ready.

Do not call an LLM. A fixed template is expected for Phase 0.

### Verifier report

`verifier-report.md` must contain:

- overall status `PASS` or `BLOCKED`;
- every claim and its `SUPPORTED`/`UNSUPPORTED` status;
- evidence references;
- exact reasons for invalid references;
- explicit statement that `PASS` is not publication approval;
- `approval_status: PENDING_HUMAN`.

### Storyboard

Generate a deterministic storyboard from the script, one section/row per script beat.

Each factual beat must include:

- beat number;
- voiceover/text;
- source claim ID(s);
- retained evidence reference(s);
- a generic visual suggestion that does not add factual claims.

Do not generate or edit video.

### Machine-readable run summary

`run.json` should contain at least:

- project name;
- verification status;
- approval status fixed to `PENDING_HUMAN`;
- counts of supported and unsupported claims;
- generated artifact paths.

Use stable ordering/formatting so repeated runs are byte-for-byte deterministic where workspace paths permit.

## Tests

Use Python `unittest`; do not add test dependencies.

Create deterministic tests under `tests/` covering at least:

1. supported claim => `SUPPORTED`;
2. missing evidence => `UNSUPPORTED`;
3. bad quote => `UNSUPPORTED`;
4. invalid line range => `UNSUPPORTED`;
5. path traversal/out-of-workspace evidence => rejected/unsupported;
6. one unsupported claim => overall `BLOCKED`;
7. supported and unsupported claims can be distinguished in the same manifest;
8. evidence references survive into report/script/storyboard where relevant;
9. identical inputs produce identical artifact contents;
10. approval status is always exactly `PENDING_HUMAN`.

Use temporary directories for mutation/negative tests. Do not modify the checked-in successful TaskPebble manifest to contain unsupported claims.

## End-to-end fixture

Use the existing TaskPebble fixture as the successful demo.

After implementation, run:

```bash
make check
make test
rm -rf examples/taskpebble/output
PYTHONPATH=src python -m rbl_content_engine examples/taskpebble/claims.json --output examples/taskpebble/output
```

Inspect all generated artifacts manually and confirm:

- all four checked-in claims are supported;
- evidence references are present;
- verifier status is `PASS`;
- approval status remains `PENDING_HUMAN`;
- no external side effects occur.

Do not commit generated `examples/taskpebble/output/` files unless there is a strong reason; they are intentionally gitignored. The tests should prove deterministic behavior instead.

## README update

Update `README.md` only as needed to document the final runnable command, artifact meanings, and test commands. Keep it concise.

Add a short Phase 1 section if needed, but **document only**. Do not implement Phase 1.

## Scope exclusions

Do not implement any of the following:

- social platform APIs;
- auto-posting;
- customer DMs/email;
- scheduled publishing;
- paid API/model calls;
- OpenAI/Anthropic/Gemini SDKs;
- browser automation;
- remote GitHub ingestion;
- database/storage services;
- embeddings/vector search;
- autonomous agents;
- video generation/editing;
- ProofLab integration;
- auto-approval.

If a proposed feature is not required to satisfy the Phase 0 exit criteria, leave it out.

## Definition of done

Phase 0 is done when:

- the CLI completes the TaskPebble run locally;
- all required artifacts are produced;
- supported/unsupported verification behaves correctly;
- unsupported claims block the result;
- evidence lineage is retained;
- deterministic tests pass;
- human approval is still mandatory;
- there is no publication or external side effect.

At the end, report:

1. files changed;
2. implementation summary;
3. commands/tests run and results;
4. example verification result;
5. any deliberate Phase 0 limitations left for Phase 1.

Do not claim success unless you actually ran the tests and the end-to-end example.

---
