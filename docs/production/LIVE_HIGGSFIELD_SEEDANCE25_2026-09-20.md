# Seedance 2.5 live verification — 2026-09-20

The official Higgsfield API smoke test has been exercised successfully by the repository owner from a local environment with owner-controlled credentials.

Verified request:

- SDK: `higgsfield-client`
- application: `bytedance/seedance-2.5/text-to-video`
- prompt: `A cinematic scene at sunset`
- duration: `5`
- resolution: `720p`
- aspect ratio: `16:9`
- credential source: ignored local `.env.local` / `HF_KEY`
- first funded-state diagnostic: provider returned `not_enough_credits`
- after API balance funding: the same smoke test completed and returned a Higgsfield-hosted MP4 URL

The generated media URL is intentionally not tracked because output URLs are runtime artifacts and may be temporary or account-specific.

This establishes the official Seedance 2.5 Text-to-Video API path as **LIVE_VERIFIED** for the owner environment as of 2026-09-20.

It does not authorize automatic social publication. Launch-video production remains subject to budget, technical QC, and human-review gates.
