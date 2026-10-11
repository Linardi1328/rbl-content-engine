# RBL Content Engine — targeted launch/compliance gate

This is an operational checklist, **not** legal advice or a certification of compliance.
Current scope: a small public informational website plus a local, operator-controlled
content-production/publishing workflow.

## Included in this change

- Accessible skip links and visible mobile navigation on all three static pages.
- Named navigation landmarks, alt text coverage checks, visible keyboard focus,
  reduced-motion styles and static regression tests.
- Safer privacy-contact instructions that do not solicit personal data publicly.
- Publishing-identifier and TikTok token-storage hardening.

## Owner sign-off required before external-customer launch

- [ ] **Dedicated private data-rights contact:** Publish a verified, monitored,
  nonpublic contact route accessible even without a prior operator relationship.
  Do not invent an email address or direct personal data into GitHub Issues.
- [ ] **Legal business details:** Confirm the real operator identity, applicable
  registration details and business contact disclosures for target markets.
- [ ] **Policy accuracy:** Verify actual data, hosting logs, platform API scopes,
  retention/deletion practices and third-party disclosures. Update legal effective
  dates on deployment, with accountable legal review as appropriate.
- [ ] **Data-request operations:** Confirm private identity verification, record
  deletion/revocation steps, handling times and lawful retention exceptions.
- [ ] **Tracking audit:** Inspect deployed cookies, SDKs, third-party scripts and
  hosting behaviors. Add consent controls only if warranted by actual collection
  and applicable jurisdictions.
- [ ] **Accessibility manual QA:** Keyboard-only and screen-reader navigation,
  mobile viewport and WCAG 2.2 AA contrast tests on the deployed version.
- [ ] **IP rights:** Confirm that logo, media, font and software SDK usage are
  appropriately licensed and that content claims can be evidenced.
- [ ] **Release gate:** One real RBL Customer Zero item must still pass the
  existing exact-asset human-approval and publication-acceptance procedure.

## Conditional features (not added without requirements)

- Checkout/refund terms and card-number/Luhn validation: no direct card payment UI.
- Email unsubscribe controls: no public marketing email subscriber flow.
- Cookie consent UI: only when relevant cookies/trackers and law require it.
- Child-account parental consent: no child-facing account/data intake in site.

Code improvements alone do not establish legal compliance. Do not market this PR
as passing any legal certification.
