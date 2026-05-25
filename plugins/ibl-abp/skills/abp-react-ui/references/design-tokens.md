# Design tokens & utility classes

Single source of truth for every visual decision in an Ibl360-style React app.
Live in `react/src/styles/globals.css`. **Never hardcode hex colors, radii,
or shadows in components** — always reach for a token. If a component needs
something that isn't a token, extend the token instead of one-offing the
component.

## Token philosophy

- **Tinted neutrals.** All grays carry a tiny amount of the brand-blue hue
  (chroma 0.005–0.015), so nothing reads as cold/clinical. No pure black,
  no pure white.
- **Restrained color strategy.** Tinted neutrals + primary blue + ≤8%
  orange accent on ONE moment per screen. Orange means "act now" — if two
  oranges are on screen, one of them is decoration and is wrong.
- **OKLCH for everything.** Lightness deltas read perceptually correctly
  across all hues, dark mode "just works".
- **Brand bicromia.** `--primary` (steel-blue) for structure/data,
  `--accent` (signal-orange) for action. Mirrors the InnobitLab wordmark.

## Surface scale (light → dark)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg-app` | warm near-white | warm near-black | global page wash |
| `--bg-sidebar` | white | one tier above app | sidebar surface |
| `--bg-card` | white | two tiers above app | cards, dialogs |
| `--bg-elev` | a clear step above card | one more tier | table headers, inputs, table-row hover backdrop |
| `--bg-row-hover` | between elev and card | between elev and row-highest | hovered table row |
| `--border-hairline` | visible 1px separator | visible 1px separator | the rare hairline (table header bottom, sidebar settings divider) |
| `--border-subtle` | barely-there separator | barely-there | optional internal subdivisions |

Surfaces stack: `app < sidebar/card < elev < row-hover`. **Always step UP** when
promoting an element (a card on the page sits on `bg-card`; a focused input
inside that card flips its background from `bg-elev` to `bg-card` ON focus —
counterintuitive, but it works: the focus "lifts" the input to match the
card, drawing the eye).

## Foreground scale

| Token | Use |
|---|---|
| `--fg-strong` | h1/h2/h3 titles, page header, KPI numbers, body emphasis |
| `--fg-default` | normal body text, table cells, paragraphs |
| `--fg-muted` | labels, meta, captions, secondary text, table column headers |
| `--fg-faint` | placeholders, disabled hints, version strings |
| `--fg-on-primary` | text rendered ON a primary-blue surface (button label, sidebar active mark) |

## Brand

| Token | Light value | Dark value | Use |
|---|---|---|---|
| `--primary` | `#2B5877` (InnobitLab `primary-600`) | brighter steel-blue | sidebar active state, primary buttons, links, focus rings |
| `--primary-strong` | darker hover | even brighter | hover variant of `--primary` |
| `--primary-soft` | `#EEF4FB` selected-nav tint | `#1F3552` selected-nav tint | active nav background, info chips, focus halos |
| `--primary-tint` | mid badge | mid badge | between soft and primary |
| `--accent` | `#F89820` signal-orange | brighter orange | the ONE moment of decisive action per screen |
| `--accent-strong` | darker hover | brighter hover | hover variant of accent |

## Semantic (state)

Used for status pills, deltas, toasts. **Don't invent new semantic colors** —
if you need "warning" use `--warning`; if you need "info" use `--info`.

| Token | Hue | Use |
|---|---|---|
| `--success` | emerald | Active, ↑ positive delta, success toast |
| `--info` | blue (cousin of primary, more saturated) | Prospect, neutral info |
| `--warning` | amber | In progress, modified, "needs attention" |
| `--error` | rose | Errors, destructive intent, ↓ negative delta |

**No additional colors.** If you find yourself wanting purple/cyan/magenta,
re-read DESIGN.md.

## Shape

| Token | px | Use |
|---|---|---|
| `--radius-sm` | 6 | tiny chips, dots |
| `--radius-md` | 8 | inputs, secondary surfaces |
| `--radius-lg` | 12 | sidebar items, dropdown items |
| `--radius-card` (`--radius-xl`/`--radius-2xl` alias) | 16 | cards, dialogs |
| `--radius-pill` | 9999 | buttons, filter chips, status pills, search input |

Buttons are **always pill** — it's a hallmark of the design. Cards are
always 16px (`rounded-2xl`).

## Elevation

| Token | Use |
|---|---|
| `--shadow-card` | every Card. Soft, layered. |
| `--shadow-popover` | dropdown menus, tooltips, select panels |
| `--shadow-dialog` | modal dialogs (heavier than popover) |
| `--shadow-toolbar` | sticky header bottom-shadow (very subtle hairline-like) |

Never use a raw `box-shadow: 0 4px 6px rgba(0,0,0,0.1)` — reach for a
shadow token.

## Type

- `--font-sans`: `Inter` loaded from Google Fonts + system fallback
- Scale ratio **1.2** (tight, product-grade — see `DESIGN.md` for the full
  scale). Reach for Tailwind utility sizes: `text-xs / sm / base / lg /
  xl / 2xl / 3xl / 4xl`.
- Weights: 400 body / 500 labels / 600 titles+buttons / 700 only on hero
- Tracking: `-0.01em` on titles (auto-applied to `h1..h4` by `globals.css`),
  `tracking-[0.06em] uppercase` on table column headers + label-md

## Tailwind utility classes available

The CSS variables above are exposed as Tailwind color/radius/shadow
utilities via `@theme inline`. The classes you'll actually type:

### Backgrounds
`bg-bg-app` · `bg-bg-sidebar` · `bg-bg-card` · `bg-bg-elev` · `bg-bg-row-hover`
`bg-primary` · `bg-primary-soft` · `bg-primary-strong` · `bg-accent` · `bg-accent-strong`
`bg-success` · `bg-info` · `bg-warning` · `bg-error`

### Foregrounds
`text-fg-strong` · `text-fg-default` · `text-fg-muted` · `text-fg-faint` · `text-fg-on-primary`
`text-primary` · `text-primary-strong` · `text-accent` · `text-success` · `text-info` · `text-warning` · `text-error`

### Borders
`border-border-hairline` · `border-border-subtle`

### Radii
`rounded-md` (8) · `rounded-lg` (12) · `rounded-xl` (16) · `rounded-2xl` (16) · `rounded-full` (pill)

### Shadows
`shadow-[var(--shadow-card)]` · `shadow-[var(--shadow-popover)]` · `shadow-[var(--shadow-dialog)]`

(Shadow tokens are exposed as CSS variables rather than full Tailwind shadow
utilities to keep the design system small. Use the bracket-notation when
applying them.)

## Dark mode

`ThemeProvider` (`@/lib/theme/ThemeProvider`) toggles a `.dark` class on
`<html>`. Every token re-defines under `.dark`. **You don't ship a separate
dark stylesheet** — the same components automatically pick up the dark
values.

The orange accent stays warm and visible in both modes. The blue primary
shifts lighter in dark mode (otherwise it would disappear against
`#13171C`). All other tokens recalibrate to keep tier hierarchy intact.

## When you need a color the tokens don't have

You probably don't. Before reaching for a hex, check:

1. Is this a state? Use `success/info/warning/error`.
2. Is this for emphasis? Use `primary` or `accent`.
3. Is this for a neutral surface? Use one of the `bg-*` tiers.

If the answer is genuinely "none of those" — talk to whoever owns the
design system before merging. The Restrained strategy survives only as
long as everyone agrees not to invent palette one-offs.

## Quick reference card (paste this in a component for visual review)

```tsx
<div className="bg-bg-app p-6 space-y-3">
  <div className="bg-bg-sidebar rounded-2xl p-4 shadow-[var(--shadow-card)]">sidebar</div>
  <div className="bg-bg-card rounded-2xl p-4 shadow-[var(--shadow-card)]">card</div>
  <div className="bg-bg-elev rounded-2xl p-4">elev</div>
  <p className="text-fg-strong text-lg font-semibold">fg-strong</p>
  <p className="text-fg-default">fg-default</p>
  <p className="text-fg-muted text-sm">fg-muted</p>
  <p className="text-fg-faint text-xs">fg-faint</p>
  <button className="bg-primary text-fg-on-primary rounded-full px-5 h-10">primary</button>
  <button className="bg-accent text-white rounded-full px-5 h-10">accent</button>
</div>
```
