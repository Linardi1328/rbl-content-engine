# Phase 5 — Direct Social Publishing

## Purpose

Phase 5 adds an RBL-owned scheduler and direct official platform adapters so a validated final video can be posted at a timezone-aware scheduled datetime without paying for a third-party scheduler.

Supported targets:

- Instagram Reels
- TikTok Direct Post
- YouTube video upload / Shorts-compatible vertical videos

Earlier Phase 0–4 publication gates remain unchanged. Phase 5 is a new, explicit owner-authorized publication milestone.

## Architecture

```text
final RBL master
-> platform-specific exports
-> explicit human approval of exact asset hashes
-> Phase 5 post manifest
-> local schedule queue
-> due-time platform publisher
-> per-platform receipt/state
```

The scheduler is intentionally conservative around uncertain writes. It marks a platform `IN_PROGRESS` before the first mutation. If the process restarts while a write is uncertain, it moves that platform to `RECONCILE_REQUIRED` rather than blindly re-posting.

TikTok is the exception where an initialized post can be safely followed by status reconciliation using its `publish_id`.

## Runtime files

All live scheduling/auth/publication state is local and gitignored. The publishing CLI automatically loads repository-root `.env.local` without overriding already-exported environment variables:

```text
.production/social-publishing-queue.json
.production/publication-receipts/
.production/social-auth/
.production/final-exports/
```

No access token, refresh token, client secret, provider ID, or private media URL belongs in tracked fixtures.

## Post manifest

See:

`examples/production/social-post-manifest.example.json`

The manifest defines:

- a stable `post_id`;
- timezone-aware `scheduled_at`;
- platform-specific video exports;
- per-platform captions/titles/configuration;
- AI-generated-media flag;
- TikTok compliance/consent receipt;
- explicit final human approval with a timezone-aware confirmation time;
- SHA-256 digests for every enabled platform asset;
- the approved external media URL where a platform publishes by URL (currently Instagram).

The scheduler never invents metadata at publish time. Final RBL publication approval is separate from TikTok's platform-specific consent. The approval hashes bind the human decision to the exact local bytes reviewed; replacing an approved file blocks preflight, scheduling, and publication until the new bytes are approved again. For URL-ingested assets, the approval also binds the exact public URL. Production staging should treat that URL as immutable after approval.

The checked-in example uses all-zero placeholder hashes only to show the schema. Do not hand-edit production hashes. Record them from the actual final files with the approval command below.

## CLI

Approve the exact current media after the human reviewer has inspected the final exports:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing approve \
  path/to/post.json \
  --human-confirmed
```

This command writes the approval timestamp and SHA-256 digest for each enabled platform asset into the manifest, plus any external media URL used by the platform. Any later change to an approved file or approved URL invalidates the approval.

Validate without network calls:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing preflight path/to/post.json
```

Schedule a post:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing schedule path/to/post.json
```

Run due posts once:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing tick
```

Run continuously:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing daemon --poll-seconds 30
```

Inspect local queue state:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing status
```

A failed or locally blocked platform can be explicitly reset after its cause is fixed:

```bash
PYTHONPATH=src python -m rbl_content_engine.publishing retry-platform POST_ID instagram
```

`RECONCILE_REQUIRED` is deliberately not reset by that command because the prior provider mutation may already have succeeded.

## Instagram Reels

Environment:

```text
INSTAGRAM_GRAPH_VERSION
INSTAGRAM_USER_ID
INSTAGRAM_ACCESS_TOKEN
```

RBL uses **Instagram API with Instagram Login**, not Facebook Login. This route does not require a Facebook Page to be linked to the Instagram professional account. It requires the `instagram_business_basic` and `instagram_business_content_publish` scopes.

The publisher creates a Reel media container against `graph.instagram.com` from a publicly reachable `video_url`, polls the container until `FINISHED`, then calls `media_publish`.

Therefore the Instagram export needs an HTTPS `public_url` in the manifest. Phase 5 does not fabricate or assume a hosting provider. Media staging/hosting must be configured separately.

The Instagram Professional account and Meta app permissions must be set up in Meta's developer console before live publication.

Official Meta Instagram workspace:
https://www.postman.com/meta/instagram/overview

## TikTok Direct Post

For reliable unattended token renewal, configure:

```text
TIKTOK_CLIENT_KEY
TIKTOK_CLIENT_SECRET
TIKTOK_REFRESH_TOKEN
```

The scheduler refreshes the short-lived access token through TikTok OAuth and stores the rotated refresh token only in ignored local state:

`.production/social-auth/tiktok.json`

For short-lived manual testing only, `TIKTOK_ACCESS_TOKEN` may be used instead.

Direct Post requirements enforced by RBL:

- query Creator Info before posting;
- requested privacy must be one of the creator's current options;
- per-post explicit consent receipt;
- creator preview recorded;
- preset caption/hashtags remain editable before consent;
- Music Usage Confirmation recorded;
- `is_aigc=true` for AI-generated RBL video;
- TikTok platform export must declare `promotional_overlay_free=true`.

TikTok's Content Sharing Guidelines prohibit applications/integrations from adding promotional branding, logos, watermarks, links, or promotional text to content sent through this API. RBL should therefore render a TikTok-specific clean export without the RBL promotional logo/brand overlay while preserving the story itself.

Unaudited Content Posting API clients are restricted by TikTok; public visibility requires the appropriate app audit/approval and `video.publish` authorization.

Official references:

- https://developers.tiktok.com/docs/en/content-posting-api-get-started
- https://developers.tiktok.com/docs/en/content-sharing-guidelines
- https://developers.tiktok.com/docs/en/oauth-user-access-token-management

## YouTube

Configure either a current short-lived token:

```text
YOUTUBE_ACCESS_TOKEN
```

or the recommended refreshable server-side credentials:

```text
YOUTUBE_CLIENT_ID
YOUTUBE_CLIENT_SECRET
YOUTUBE_REFRESH_TOKEN
```

The adapter uses YouTube's resumable upload flow. RBL sets:

- title;
- description;
- tags;
- category;
- language;
- made-for-kids status;
- synthetic-media disclosure.

When intentionally called before the manifest's scheduled datetime, the adapter uses YouTube's native scheduling contract: `privacyStatus=private` plus `status.publishAt`. In the normal RBL daemon flow, the scheduler waits until the due time and publishes then.

New/unverified YouTube Data API projects can be restricted to private uploads until Google completes the required audit.

Official reference:
https://developers.google.com/youtube/v3/docs/videos/insert

## Scheduling semantics

`scheduled_at` must be ISO-8601 with a timezone offset, for example:

```text
2026-10-02T19:30:00+08:00
```

The queue sorts by absolute time and publishes any due platform on the first scheduler tick at or after that instant.

A platform failure does not roll back or re-post successful platforms.

## One-time provider setup still required

Phase 5 implements the API clients and scheduler, but provider developer accounts cannot be truthfully created or approved by repository code.

Before first live publication, the owner must complete the respective provider setup:

1. Meta developer app + Instagram Professional account + Instagram Login + `instagram_business_basic` / `instagram_business_content_publish` permissions.
2. TikTok developer app + Login/OAuth + Content Posting API + `video.publish` approval/audit.
3. Google Cloud project + YouTube Data API + OAuth consent/client + any required compliance audit.
4. Public HTTPS media hosting for Instagram's Reel `video_url`.

After those prerequisites are connected and tokens are configured locally, the scheduler can execute a due Phase 5 manifest only after the final platform assets have been explicitly human-approved and their current SHA-256 hashes still match. TikTok Direct Post additionally retains its separate per-post platform consent requirements.
