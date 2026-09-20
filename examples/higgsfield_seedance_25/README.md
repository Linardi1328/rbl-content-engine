# Higgsfield Seedance 2.5 SDK smoke test

This example follows Higgsfield's official Python SDK documentation and uses:

`bytedance/seedance-2.5/text-to-video`

with:

- prompt: `A cinematic scene at sunset`
- duration: `5`
- resolution: `720p`
- aspect ratio: `16:9`

The request is billable.

## Install

From the repository root:

```bash
uv sync --locked
```

## Configure credentials locally

Do **not** paste the API key into chat or commit it.

Run:

```bash
uv run python scripts/configure_higgsfield_env.py
```

Enter the credential only in your local terminal when prompted. The helper writes:

```text
.env.local
```

with the logical format:

```text
HF_KEY=key-id:key-secret
```

The file is gitignored and written with restrictive permissions.

## Run the billable smoke test

```bash
uv run python examples/higgsfield_seedance_25/main.py
```

Success is reported only by printing the generated video URL.

Failed, canceled, moderated, credential, API, or malformed-result cases exit non-zero and do not claim success.
