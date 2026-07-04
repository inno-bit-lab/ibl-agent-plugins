# Verified analysis — abp-react-ui visual verification

Self-contained excerpt of the adversarially-verified reflection for this artifact.

## Summary

Step 6 "Verify" is static only (tsc/build). Runtime visual verification is blocked
on ABP+React: the preview browser can't pass OIDC login, and the raster screenshot
times out at 30s even on a loaded page. With no guidance, the agent worked blind
and committed a regression.

## Evidence

- `Termocasa-react 40e4cc13` — "la verifica via browser è murata dal login/cert OIDC ...
  Ho lavorato alla cieca e per questo ho sbagliato"; RfqFormPage regression
  (commit f8efd52, later amended).
- `Termocasa-react ef0234e1` — `preview_screenshot timed out after 30s` on a loaded SPA;
  "lo snapshot funziona".
- `Termocasa-react d4a5e42e` — "disattivo temporaneamente animazioni/transizioni" (reused twice).
- `Termocasa-react c2a2463d` — structured offline fallback (adversarial review + contract + i18n).

## Adversarial verification

- Confirmed: 7 sessions (4 strong), ~20-25 point events. Recurrence concentrated on
  Termocasa (6/7); 1 is Keycloak (`FlowGest 0e0bc24e`), not ABP.

## Claims REJECTED by verification — do NOT encode

- "token via password grant with `.Trim()`" — 0 occurrences in any transcript.
- "dev cert not trusted" — contradicted by `ef0234e1` (discovery fetch returned 200).
- "12 timeouts in one session" — false; real max is 4.

## Note on portability

The reference must be written host-agnostically ("your host's preview/snapshot
tool"), NOT anchored to `preview_snapshot` / `preview_screenshot` (Claude Preview only).

Source: reflection over `~/.claude` session transcripts. Session ids are opaque; no secrets present.
