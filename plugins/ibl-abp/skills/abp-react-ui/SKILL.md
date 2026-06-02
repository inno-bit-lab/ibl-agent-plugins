---
name: abp-react-ui
description: 'Build or modify the React UI layer for an ABP backend while reusing existing shared components and design tokens. Use after abp-feature-dev scaffolds an entity, before editing react/src/pages, react/src/lib/api, react/src/components, router, or route config, and when wiring typed API clients, CRUD pages, smart filters, lifecycle actions, permissions, menu entries, tenant switching, TanStack Query, react-hook-form, shadcn, i18n, responsive tables/cards, or FAB actions. Supports create, modify, and delete UI workflows.'
---

# ABP + React UI

End-to-end React UI work on top of an ABP backend, with **mandatory reuse of
the existing shared components and design tokens**. The biggest mistake to
avoid is rolling a new button / card / status badge / spinner when the
project already ships one — inconsistency here is how the product starts
to feel sloppy.

This skill **assumes** the backend follows `abp-feature-dev` / `abp-mongodb`
conventions: typed `Get{Entities}Input` filters, enum names as strings on
the wire, multi-tenant permissions, name-based localization keys,
case-insensitive `.ToLower()` search.

These React patterns are the same whether the backend uses the nolayers
(single-project) or the layered ABP template. ABP generates the same REST
endpoints (`/api/app/{entity-kebab}/...`) and DTO shapes from the AppService
either way, so the API client, CRUD page, routing, sidebar, and i18n are
unchanged — the only backend-shaped thing the UI consumes is the generated
API/DTO contract, which is identical across templates.

If the backend feature belongs to a module, use `abp-module-architecture`
before editing React. Module-owned pages, API clients, and route/menu entries
belong under that module's `react/src`; only reused components/primitives go
to Shared UI.

## The three rules

1. **Reuse before invent.** Every CRUD UI is assembled from the standard
   library in `shared-components.md`. If you find yourself writing
   `<button className="...">` from scratch, stop — use `<Button>`. Same
   for cards, dialogs, tables, status pills, tooltips.
2. **Tokens before hex.** Every color, radius, shadow has a token in
   `design-tokens.md`. Hardcoding `#2B5877` or `rgb(...)` in a component
   breaks dark mode and future palette tweaks. Use `bg-primary` /
   `text-fg-strong` / `rounded-2xl` etc.
3. **The contract drives the UI.** When a new ABP AppService lands, the
   shape of the UI is mostly mechanical: see `data-fetching.md` for the
   hand-off.

## When to read which reference

| Working on… | Read |
|---|---|
| **Colors, radii, shadows, type — anything visual** | `references/design-tokens.md` |
| **Buttons, cards, dialogs, tables, status pills, tooltips, hooks** | `references/shared-components.md` |
| **Wiring a backend contract into the UI (axios, TanStack Query, mutations, debounced search, permissions)** | `references/data-fetching.md` |
| Typed API client per entity | `references/api-client.md` |
| CRUD page layout (filters, table, dialog, FAB) | `references/page-pattern.md` |
| **Complex entity (≥10 fields, value objects, embedded lists)? Dedicated `/{plural}/new` + `/{plural}/:id/edit` page with tabs** | `references/complex-edit-page.md` |
| **Abstract base class? Customer/Supplier share a `BusinessParty` base** | `references/abstract-base.md` |
| Adding a route + sidebar entry (groups, fallbackName, RailTooltip) | `references/routing-menu.md` |
| Tenant switcher chip — one-time project setup | `references/tenant-switch.md` |
| i18n keys, ABP localization fetch, fallback inline pattern | `references/i18n.md` |
| Form validation with React Hook Form + Zod | `references/forms.md` |
| Modifying or deleting an existing UI feature | `references/modify-delete.md` |

## Modular React placement

For modular ABP projects, prefer:

```text
modules/<feature-module>/react/src/
  module.ts
  pages/
  components/
  lib/api/

modules/<shared-module>/react/src/
  components/ui/
  hooks/
  lib/
```

The host React app keeps shell concerns only: auth, theme, layout, tenant
switch, root router, and `src/modules/registry.ts`.

After moving React files outside `react/src`, update all three:

- Vite aliases (`@ibl360/<module>-ui`)
- TypeScript paths/includes
- Tailwind v4 sources:

```css
@source "../../../modules/ibl360shared/react/src";
@source "../../../modules/ibl360crm/react/src";
```

Symptom if Tailwind is missed: the app renders but module pages/components look
unstyled or partially styled.

## When you absolutely must run this skill

- `abp-feature-dev` just finished scaffolding an entity — the contract is
  ready. Start with `data-fetching.md` and walk the checklist.
- The user is editing files under `react/src/lib/api/`, `react/src/pages/`,
  `routes/router.tsx`, `lib/routing/route-config.ts`, or
  `components/layout/*`. The conventions in this skill must be respected
  even for one-line changes.
- The user mentions UI, page, menu entry, permission guard, tenant
  switch, i18n keys, debounced search, table, dialog, button — even
  tangentially.

## The three workflows

### CREATE — new entity, new page

Run after `abp-feature-dev` has produced the entity + AppService. The
shape is mechanical once you know it.

#### Step 1 — Detect the React app

Look for a `react/` or `react-public-web/` directory whose `package.json`
references `@tanstack/react-router` or `@volo/abp-react-oidc-auth`.
Usually `react/` (internal admin). If neither exists, this skill does
NOT apply — say so and stop.

#### Step 2 — Confirm the user wants a UI (unless already explicit)

If the user already said "scaffold the full feature with UI", skip.
Otherwise:

```
You have an AppService for {Entity}. Want me to add the React UI now?
  - yes → I'll add API client + CRUD page + route + sidebar entry + i18n keys
  - no  → backend only; the API is consumable at /api/app/{entity-kebab}
[default: yes — the feature is only useful when users can interact with it]
```

#### Step 3 — Choose menu placement

Three sensible positions for a CRUD entity in `route-config.ts`:

```
Where should the {Entity} menu entry appear?
  1. Top-level under "OVERVIEW" group     [default for first-class entities]
  2. Under "ADMIN" group                  [for admin/config tools]
  3. No menu entry — page reachable only by direct URL
     (admin utilities, debug pages, entities reachable only from a parent)
```

Show the current sidebar items by reading `route-config.ts` so the
choice is informed. Pick an `order` that fits.

#### Step 4 — Dialog vs dedicated edit page

**Decide before scaffolding the page.** Two patterns, pick by entity
shape:

```
How many fields will the create/edit form have, end to end?

A) ≤ ~8 flat fields, no nested value objects, no lists.
   → DIALOG inside the list page. Modal opens, user fills, saves, dialog
     closes. The list page is the only UI artifact.
     Pattern: see references/page-pattern.md (CRUD page with inline Dialog).

B) ≥ ~10 fields, OR ≥1 value object (Address, embedded sub-document),
   OR ≥1 list of items (Socials, CustomFields, multiple addresses),
   OR multiple semantic groups (identity / contact / financial / status).
   → DEDICATED EDIT PAGE at /{plural}/new and /{plural}/:id/edit.
     The list page navigates to it on "New" and on row-click ("Edit").
     The dialog gets in the way — too tall on mobile, scrolls badly,
     no room for tabs, no way to group fields.
     Pattern: see references/complex-edit-page.md.
```

**Critical signal for B**: if you see a `BusinessParty`-like base class
on the backend with VO arrays (BillingAddress/ShippingAddresses,
Socials, CustomFields) and ≥3 semantic field groups, the dialog is the
wrong tool. Don't try to cram it. Go straight to the dedicated page.

If you picked B, read `complex-edit-page.md` and follow its template:
TabsStrip + EditPageShell + reusable field-group components.

#### Step 5 — Scaffold the files

Walk the **end-to-end checklist** in `data-fetching.md` ("When the
backend contract is ready, you walk this list"):

1. **`lib/api/{entityCamel}.ts`** — typed API client mirroring the
   backend DTOs. See `api-client.md` for the template and
   `data-fetching.md` for the wiring patterns.
2. **`pages/{plural}/{Entity}Page.tsx`** — the CRUD page. **Composed
   entirely from `shared-components.md` primitives** — Button, Card,
   Input, Select, Table, StatusPill, ConfirmDialog, Dialog +
   `useDebouncedSearch`. See `page-pattern.md` for the full template
   that you can adapt by changing field/filter names.
3. **Routes** — in a modular app, expose routes from the module's
   `react/src/module.ts` and register the module in the host registry. In a
   non-modular app, add them directly to `routes/router.tsx`. Use the owning
   module permission namespace, e.g.
   `createPermissionGuard('Ibl360Crm.Customers')`, not the old host namespace.
4. **Menu entries** — in a modular app, put sidebar entries in the module's
   `menuItems`; the host `route-config.ts` should merge module entries. In a
   non-modular app, edit `lib/routing/route-config.ts`. Every entry needs
   `fallbackName`, `icon`, `order`, `group`, and the owning module
   `requiredPolicy`.
5. **Localization keys** in **every** project language file
   of the owning resource. For module-owned UI this is the module resource
   (`modules/<module>/<Module>.Contracts/Localization/<Module>/{it,en,fr,es}.json`),
   not the host resource. See `i18n.md` for the canonical list of keys per
   CRUD page. **Use `{{name}}` not `{name}`** for interpolations —
   react-i18next wants double braces.
6. **TenantSwitch** — one-time project setup; only if the app doesn't
   already have one. See `tenant-switch.md`.

#### Step 6 — Verify

```bash
npx tsc --noEmit -p tsconfig.app.json
```

Should be clean for your new files (pre-existing errors in test files
or stale enums are not yours to fix).

For modular moves, also run `npm run build`; Vite validates aliases and the
CSS output size often reveals whether Tailwind picked up module sources.

Tell the user to **hard refresh** (Ctrl+F5) before testing — the React
app caches the i18n bundle and won't see new keys until invalidated.

#### Step 7 — Polish pass with `impeccable` (recommended for complex pages)

For any entity that took the **dedicated edit page** path (Step 4 B), a
polish pass is non-negotiable: dialog forms self-correct on small screens
because the modal is full-bleed on mobile, but a multi-tab form has many
more places to break. Invoke the `impeccable` skill scoped to the new
files:

```
Skill: impeccable
Args: Review responsive layout, tap targets, sticky chrome, nested cards,
      and a11y on react/src/pages/{plural}/* and any reusable component
      added to react/src/components/business-party/ (or wherever you put
      the shared editors). Apply Critical/High fixes inline. Run tsc.
```

Specific things impeccable catches that you'll otherwise ship broken:
- Editable list rows with grid `[fixed_px | 1fr | auto]` that explode
  on viewport <500px (the URL/value input collapses to "https://x.")
- 32×32 icon buttons next to focusable inputs (mis-tap rate is high
  on touch; the bar is 40×40 at the smallest)
- Edit page action bar (Save/Cancel) at the top with no sticky;
  scrolling kills primary affordance on mobile
- Tab strip with `overflow-x-auto` and no fade indicator → users
  don't discover off-screen tabs
- Native `<input type="checkbox">` rendered raw (browser default
  looks awful next to themed inputs); use the project Checkbox
  primitive or add one to `components/ui/checkbox.tsx`
- Nested cards (card-in-card) — the shared design law forbids it;
  use dividers between rows instead

### MODIFY — change an existing UI feature

> **No scripts.** Every change is contextual: a renamed property cascades
> across API types, page columns, filters, validation schema, locale keys.
> Claude greps → understands → edits, not scaffold-overrides.

Workflow:

1. **Identify the change** (rename property, add filter, change
   permission policy, add lifecycle transition, swap table column,
   change form layout).
2. **Find every file that references what you're changing.** Grep
   liberally. See `modify-delete.md` for impact maps per change type.
3. **Edit each file** following the existing patterns (don't drive-by
   refactor unrelated code).
4. **`tsc`** scoped to changed files. Hard refresh once both backend +
   React are running.

### DELETE — remove a UI feature

Cleanly removing means tracking down every reference, not just deleting
the page file. Order matters — leave a route or sidebar reference
dangling and the React app crashes at boot.

Order:
1. `route-config.ts` (invisible)
2. `router.tsx` (route + import)
3. `pages/{plural}/` (page folder)
4. `lib/api/{entityCamel}.ts` (API module) — grep imports first!
5. Locale `.json` (each language, show diff before applying)

**Don't touch the backend automatically.** If the user wants the
backend gone too, delegate to `abp-feature-dev` "Removing a feature".

See `modify-delete.md` for the full checklist.

## Conventions enforced (the bar to clear before merging)

- **Reuse from `shared-components.md`**, don't reinvent.
- **Tokens from `design-tokens.md`**, don't hardcode hex / px shadows.
- **TS string unions for backend enums**, not TS numeric enums.
- **Name-based i18n keys** for enum values (`Enum:X.Active`, not `.1`).
- **`fallbackName`** on every sidebar entry.
- **`createPermissionGuard`** on every protected route + `usePermissions`
  per-button visibility.
- **`__tenant` header** is handled by the axios interceptor — never
  add it manually.
- **`useDebouncedSearch`** for any text filter that hits the backend
  (≥2 chars, 350ms debounce, spinner + hint).
- **RHF + Zod** for forms (no manual `useState` for inputs).
- **Edit forms use the remount-on-id pattern**: thin outer wrapper loads
  the entity + renders `<XxxForm key={existing?.id ?? 'new'} existing={…} />`;
  the inner calls `useForm({ defaultValues: existing ? fromDto(existing) : defaults() })`.
  Never `useForm + useEffect(() => form.reset(fromDto(existing)), [existing])`
  in the same component — that pattern silently breaks every Radix Select
  bound via `<Controller>` (stale hidden `<select>` + placeholder in the
  trigger). See `forms.md` → "Edit mode — the remount-on-id pattern".
- **Use `<Field>` from `@/components/ui/field.tsx`** for every labelled
  form field. Don't redeclare a local `Field` helper.
- **TanStack Query** for fetching (no `useEffect + fetch`); every
  mutation invalidates the list query key on success.
- **Tables collapse to card-list below `lg` (1024px)**; mobile gets a
  `bg-accent` FAB in the bottom-right for the primary action.
- **No 1px borders to separate sections** (use background tier shifts
  + the rare `border-hairline` for the table-header bottom only).
- **No nested cards.** If a section needs its own visual group, use
  divider lines between rows or a single inset background tint —
  never a `border border-… p-4` inside another `border border-… p-4`.
- **Editable list rows MUST stack on mobile.** Pattern
  `grid-cols-[1fr_auto] sm:grid-cols-[FIXED_PX_1fr_auto]`, with the
  first sm column `col-span-2 sm:col-auto`. Fixed-px first column
  without a mobile override always blows up the second one.
- **Tap target floor = 40×40 (`h-10 w-10`)** for any button next to
  a focusable input. Smaller is fine in isolation (table row menus)
  but next to inputs the mis-tap rate is unacceptable.
- **Native `<input type="checkbox">` is banned** in business forms.
  Use the project `components/ui/checkbox.tsx` primitive (or add
  one — it's ~40 lines, no extra dep).
- **Edit pages with tabs MUST use `EditPageShell` + `TabsStrip`**
  (or copy the chrome from `references/complex-edit-page.md`).
  Sticky header on every breakpoint, mobile bottom action bar,
  tab fade indicators on `<lg`, focus rings — all in the shell.

## The "is it ready" smoke test

After every Create, walk this list with the user before declaring done:

1. `tsc` clean for new files
2. Hit the page as a tenant admin user
3. Permission gate works (logout / log in as user without permission →
   redirected to `/403`)
4. Tenant switch works (Host → demo via header chip → list refreshes)
5. i18n labels resolve (hard refresh first; verify IT and EN)
6. Insert / update / delete round-trip OK
7. Search debounces + shows "min N chars" hint
8. Lifecycle action (if present) refuses invalid transitions with the
   localized backend error message in a toast
9. Mobile (<768px): drawer + card-list + FAB visible
10. Tablet (768–1024): sidebar collapsed rail + card-list still
11. Dark mode toggle works (Sole/Luna icon in header)
