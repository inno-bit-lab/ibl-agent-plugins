# Improvement

## Proposed Change

New `references/visual-verification.md`, linked from SKILL.md Step 6 "Verify"
(and Step 7 polish), covering — in **host-agnostic** terms:

1. **Tool hierarchy.** Prefer the host's DOM snapshot / inspect / eval over a
   raster screenshot; take a raster screenshot only after injecting a style that
   zeroes `animation`/`transition` (the reused d4a5e42e workaround).

2. **OIDC wall recognition.** Redirect to the auth port (`:44366`), an "error
   page" interstitial → make an explicit decision: delegate the login to the user
   or ask for a screenshot; do NOT retry blind. Say plainly that a blocked login
   means "verify via code, not via pixels".

3. **Structured offline fallback.** When auth is walled: adversarial code review
   + API-contract check + i18n check (the c2a2463d pattern), instead of declaring
   a page "clean" from source only.

Write it referring to "your host's preview/snapshot/inspect tool", never to
`preview_snapshot` / `preview_screenshot` (those are Claude Preview only).

## Rationale

Host-agnostic once phrased abstractly: the guidance is prose, and the concrete
danger (a regression committed while working blind) is real and cost an amended
commit. Adding it as a `references/` file (not a new skill) avoids touching
`PLUGIN_SKILLS` or the manifests.

## Scope

- In: a new reference + a SKILL.md link from the Verify/Polish steps.
- Out: the rejected claims above (password-grant/.Trim, dev-cert-not-trusted,
  "12 timeouts") — they must not be codified.

## Risks

- Do NOT anchor to Claude Preview tool names, or the reference is useful only on
  Claude Code. Phrase in terms of generic "preview auth (OIDC)".
- Recurrence is concentrated on one project (6/7 sessions Termocasa; 1 is
  Keycloak, not ABP) — keep the reference about the general "walled preview auth"
  shape, not Termocasa specifics.
- The raster-timeout tactics depend on the host's preview tooling and may go
  stale; keep them in `references/` so they are easy to update.
