# Visual Verification

Use this reference after static React checks when you need confidence that an
ABP + React page actually renders correctly, or when browser verification is
walled by authentication.

## Prefer inspectable state over pixels

Use your host's DOM snapshot, inspect, console, or browser-eval tool before a
raster screenshot. Structured DOM state survives webfont delays, animations, and
slow screenshot capture better than pixels.

Good evidence:

- current URL and route
- whether the page reached the expected component or is stuck at auth
- visible headings, buttons, form labels, validation messages, and table rows
- disabled/enabled state for primary actions
- console errors and failed network calls

Use a raster screenshot only when layout, spacing, or responsive behavior is the
thing being verified. Before taking it, temporarily disable animations and
transitions through your host's browser tooling:

```css
*, *::before, *::after {
  animation: none !important;
  transition: none !important;
  caret-color: transparent !important;
}
```

Do not keep retrying screenshots if the DOM snapshot already proves the page is
loaded or blocked. Switch evidence type.

## Recognize the OIDC wall

ABP React apps often redirect to a separate auth host/port for OIDC. If the
preview lands on an auth redirect, an interstitial error page, or a certificate
login wall, make an explicit decision:

- ask the user to complete login in the interactive browser
- ask the user for a screenshot from their authenticated browser
- fall back to offline verification

Do not keep retrying unauthenticated page loads and then claim visual confidence.
A blocked login means verify via code and inspectable contracts, not via pixels.

## Offline fallback when auth is walled

When runtime preview is blocked, run a structured offline review before calling
the UI ready:

1. **Adversarial component review:** read the page, form, table/card layout,
   route, and menu entry looking specifically for stale props, missing guards,
   wrong fallback labels, mobile overflow, nested cards, and unmanaged loading
   or error states.
2. **API contract check:** compare the typed API client and DTO usage against
   the generated backend contract. Confirm enum strings, filters, IDs,
   mutation payloads, and invalidation keys.
3. **Permission and routing check:** confirm route guards and menu
   `requiredPolicy` use the owning module permission namespace, not a stale host
   namespace.
4. **i18n check:** verify each visible label, table column, empty state, toast,
   validation message, and enum label has keys in each project language file.
5. **Responsive reasoning:** inspect grid classes and fixed widths. Editable
   list rows must stack on mobile; action buttons near inputs need 40x40 tap
   targets.

Report the fallback honestly: "runtime preview was auth-walled; verified by
code/contract/i18n review" plus the commands and files checked.

## Ready criteria

For a normal authenticated path:

- static checks passed (`tsc`, and `build` for modular moves)
- route loads or the auth wall is explicitly identified
- DOM snapshot or equivalent confirms the expected page state
- raster screenshot is used only when layout is the question, with animations
  disabled first

For an auth-walled path:

- no blind visual claim
- offline fallback completed
- remaining runtime risk is stated plainly for the user to verify in their
  authenticated browser
