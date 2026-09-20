# Phase 4A — Official Higgsfield API Launch Video

## Purpose

Phase 4A adds Higgsfield's official pay-as-you-go API as a real RBL generation backend and prepares the first complete launch video for Instagram Reels, TikTok, and YouTube Shorts.

The final video must stop at:

`PENDING_HUMAN_REVIEW`

No social publication may occur until the human owner explicitly approves the final cut.

## Official API

Use the official Python SDK:

`higgsfield-client>=0.1.0,<0.2.0` plus `python-dotenv>=1.0.0,<2.0.0`

Credentials are supplied only through environment variables:

```bash
export HF_KEY="KEY_ID:KEY_SECRET"
```

or:

```bash
export HF_API_KEY="KEY_ID"
export HF_API_SECRET="KEY_SECRET"
```

Never place credentials in tracked JSON, source code, shell scripts, examples, screenshots, logs, or documentation.

The SDK defaults to `https://api.higgsfield.ai`.

## Account funding prerequisite

The Higgsfield API has a prepaid USD balance separate from the creator/plugin subscription balance.

Before the first live generation:

1. sign in to Higgsfield Cloud;
2. create an API key;
3. save the full secret because it is shown only once;
4. top up the API balance;
5. use the minimum practical prototype amount (currently US$5 minimum, subject to live provider policy);
6. put the credentials into the local runtime environment only.

The current ChatGPT Higgsfield integration does not expose key creation or Cloud payment/top-up mutations. Do not mark this prerequisite complete unless the human has actually completed it or an authorized live tool reports it.

## Install

Use the repository's existing package manager and lockfile:

```bash
uv sync --locked
```

The official SDK and dotenv loader are now part of the locked Python environment. Network/API execution still occurs only when a live Higgsfield action is explicitly run.

## Seedance 2.5 SDK smoke test

Official application path:

`bytedance/seedance-2.5/text-to-video`

Local-only credential setup:

```bash
uv run python scripts/configure_higgsfield_env.py
```

This prompts for `HF_KEY` in the local terminal with hidden input and writes ignored `.env.local` in `key-id:key-secret` format. Never paste the key into chat.

Billable smoke test:

```bash
uv run python examples/higgsfield_seedance_25/main.py
```

The example uses the official synchronous `higgsfield_client.subscribe()` call with:

- prompt `A cinematic scene at sunset`;
- duration `5`;
- resolution `720p`;
- aspect ratio `16:9`.

A URL is printed only after successful terminal completion. Failed, canceled, moderated, credential, API, or malformed-result states exit non-zero and do not claim success.

## Launch plan

Tracked plan:

`examples/production/rbl-launch-video-plan.json`

Target:

- 9:16;
- approximately 20 seconds;
- five controlled 4-second shots;
- Instagram Reels;
- TikTok;
- YouTube Shorts;
- per-project budget cap US$20.

The tracked plan deliberately uses:

`LIVE_CATALOG_REQUIRED`

for every Higgsfield API application path. Before execution, resolve each shot against the live current Higgsfield Cloud catalog. Never guess or preserve a stale model endpoint because a previous provider surface used a similar model name.

## Production flow

```text
verified RBL launch claims
-> launch plan
-> live Higgsfield API catalog
-> resolve application/model per shot
-> current USD quote / estimate
-> project-budget check
-> submit exactly one request
-> retain request ID
-> wait/poll original request
-> capture output URL
-> QC
-> targeted retry only when justified
-> assemble final 9:16 cut
-> PENDING_HUMAN_REVIEW
-> HUMAN REVIEW
-> APPROVED_FOR_PUBLICATION or REJECTED
```

A timeout or uncertain submission outcome must never trigger an automatic paid resubmission.

## Spend controls

Initial launch cap:

`US$20`

This is tighter than the repository's broader prototype ceiling.

For every shot:

- retain its quoted USD cost;
- require the aggregate estimate to remain within the project cap;
- count all submitted retries in actual spend;
- never silently translate plugin credits into API USD;
- stop before a submission that would exceed the cap.

The launch plan currently budgets US$15 across five shots, leaving US$5 of project headroom for targeted retries or finishing costs.

## Official adapter

`src/rbl_content_engine/production/higgsfield_api.py`

The adapter:

- lazy-loads `higgsfield_client.SyncClient`;
- lets the official SDK read `HF_KEY` or `HF_API_KEY` + `HF_API_SECRET`;
- uploads reference files through the official SDK;
- submits one application request;
- records the observed request ID;
- waits on the same request controller;
- extracts common image/video result URLs;
- never retries billable mutations itself.

## Review gate

`src/rbl_content_engine/production/launch.py`

A completed launch cut can only transition to:

`PENDING_HUMAN_REVIEW`

when:

- every planned shot has a result;
- every shot passed QC;
- aggregate actual spend is within the project budget;
- a final video URL exists.

Generation success does **not** imply publication approval.

Only:

`approve_for_publication(..., human_confirmed=True)`

may produce:

`APPROVED_FOR_PUBLICATION`

No function in Phase 4A publishes to a social network.

## Launch messaging

The first launch video should communicate the repository's actual workflow rather than promise outcomes:

1. most AI content starts with a prompt;
2. RBL starts with evidence;
3. claims are verified before packaging;
4. verified content is adapted to platform-native treatments;
5. generation runs under reference/QC/budget controls;
6. a human reviews before publication.

Avoid claims about guaranteed virality, reach, sales, or algorithmic preference.

## Exit condition

Phase 4A implementation is repository-complete when CI passes and the official adapter/review gate are merged.

Operational completion requires:

- funded Higgsfield API account;
- owner-controlled API credentials in the runtime;
- current live model/application paths;
- successful generated launch shots;
- QC-passed final assembled video;
- final state `PENDING_HUMAN_REVIEW`.

Stop there and present the final video to the human owner.

Do not publish until the human explicitly approves it.
