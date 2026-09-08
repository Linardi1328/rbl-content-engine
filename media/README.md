# Media staging

Use this folder as the manual source-asset inbox for RBL Productions content work.

## Good candidates

- Raw or approved photos, short video clips, audio, thumbnails, and graphics
- Brand assets and reusable overlays
- Public-safe screenshots and reference visuals
- Test/demo assets for content-pipeline development

## Workflow

1. Manually place source assets in `media/` (create descriptive subfolders when useful).
2. Treat files here as source material, not automatically publishable output.
3. Content-processing code should explicitly read, transform, or copy approved assets into its own generated/output locations.
4. Keep human approval boundaries before publication.

## Public-repository rule

This repository is public. Do not commit private client material, unreleased confidential campaigns, credentials, private personal data, or media without appropriate usage rights.

## File conventions

- Prefer descriptive lowercase kebab-case filenames.
- Preserve originals where practical.
- Avoid duplicate exports and unnecessary large intermediates in Git history.
- For production-scale video/audio, use appropriate external storage when repository-based storage stops being practical.
