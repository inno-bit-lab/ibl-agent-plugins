# Problem

## Affected Skill

- Skill: abp-react-ui
- Plugin: ibl-abp
- Agent/Host: claude (observed); the reference must be written host-agnostically

## What Happened

The skill's Step 6 "Verify" is static only (`tsc --noEmit`, `npm run build`).
On ABP+React projects the runtime visual verification is blocked: the preview
browser cannot pass the OIDC login (redirect to `:44366`, an "error page"
interstitial), and the screenshot times out at 30s even on a loaded page
(webfonts / animations). With no guidance for this, the agent **worked blind and
committed a regression** (RfqFormPage). The workarounds that do work — prefer a
DOM snapshot over a raster screenshot, disable animations before capturing,
recognize the OIDC wall and delegate the login, fall back to an offline
adversarial review — are re-derived from scratch each time. No file in the skill
mentions preview, screenshot, or auth-wall handling today.

## Expected Behavior

- The skill has a visual-verification reference that establishes a tool hierarchy
  (DOM snapshot/inspect before raster screenshot; screenshot only after disabling
  animations), teaches recognition of the OIDC wall with an explicit decision
  (delegate login or ask for a screenshot — never retry blind), and a structured
  offline fallback (adversarial review + API contract + i18n) when auth is walled.

## Expected Behavior — written host-agnostically

The reference must speak in terms of "your host's preview/snapshot tool", not the
Claude Preview tool names, so it is useful on Codex, Claude Code, Antigravity, and
OpenCode.

## Evidence

- `Termocasa-react 40e4cc13` — "la verifica via browser è murata dal login/cert
  OIDC ... Ho lavorato alla cieca e per questo ho sbagliato"; regression RfqFormPage
  (commit f8efd52, later amended).
- `Termocasa-react ef0234e1` — `preview_screenshot timed out after 30s` with the
  SPA loaded; "lo snapshot funziona".
- `Termocasa-react d4a5e42e` — "disattivo temporaneamente animazioni/transizioni e
  riprovo" (reused twice).
- `Termocasa-react c2a2463d` — structured offline fallback (adversarial review +
  contract + i18n).
- Verified analysis (self-contained): `attachments/verified-analysis.md`.
  Adversarial verification confirmed 7 sessions (4 strong), ~20-25 point events,
  concentrated on Termocasa (6/7).

## Claims the verification REJECTED — do NOT encode

- "token via password grant with `.Trim()`" — 0 occurrences in any transcript.
- "dev cert not trusted" — contradicted by `ef0234e1` (discovery fetch returned 200).
- "12 timeouts in one session" — false; real max is 4.
