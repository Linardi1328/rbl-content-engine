# YouTube private live verification — 2026-09-23

The RBL Content Engine YouTube publishing path has been exercised successfully by the repository owner against the real RBL Productions Official channel using owner-controlled Google OAuth credentials.

Verified authorization path:

- Google OAuth client type: Desktop app
- scope: `https://www.googleapis.com/auth/youtube.upload`
- authorization mode: installed-app loopback callback with PKCE
- long-lived state: refresh token persisted only under ignored `.production/social-auth/youtube.json`
- token-state file mode observed locally: owner-only read/write
- no OAuth secret, access token, refresh token, or authorization URL is tracked in the repository

Verified upload:

- smoke-test post ID: `RBL-YT-SMOKE-001`
- source asset: final Dragon Princess Episode 1 review export
- requested YouTube visibility: `private`
- scheduler terminal state: `COMPLETE`
- platform adapter state: `PUBLISHED`
- YouTube video ID: recorded in the local ignored publication receipt (redacted here)
- YouTube Studio verification: upload appeared on the RBL Productions Official channel with **Private** visibility

The adapter's `PUBLISHED` state means the YouTube upload mutation completed successfully. It does **not** mean the video's YouTube visibility is public; visibility remains governed by the manifest's `privacy_status` and, when used, YouTube's native `publishAt` scheduling contract.

This establishes the YouTube OAuth, refresh-token, resumable-upload, provider-ID, scheduler-state, and receipt path as **PRIVATE_LIVE_VERIFIED** for the owner environment as of 2026-09-23.

It does not establish unrestricted public API publishing for a new/unverified Google API project. Public/scheduled production use remains subject to applicable YouTube API project verification/audit requirements and the existing RBL exact-asset human approval gate.
