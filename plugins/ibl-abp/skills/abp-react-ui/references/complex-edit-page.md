# Complex edit pages (tabs, shells, reusable field groups)

This reference covers the **dedicated edit-page pattern** for entities
that have too many fields to fit comfortably in a dialog. Use the
decision table in SKILL.md Step 4 to choose between dialog and page.

Anchor example in the codebase: **CustomerEditPage** and
**SupplierEditPage**. They share an `EditPageShell` + `TabsStrip` chrome
and reusable field-group components in
`react/src/components/business-party/`.

## When this pattern is right

All three of these are usually true at once:

- **≥ 10 form fields** at the leaf level (excluding nested VOs).
- **Value objects or embedded lists** that need their own sub-UI
  (postal addresses, social links, custom-fields key/value pairs,
  multiple shipping addresses with a default).
- **≥ 3 semantic groups** that the user expects to find separately:
  identity vs. contact vs. billing vs. status vs. integrations.

If any of these is missing, prefer the dialog. The dialog is faster to
build and keeps users in the list context. Only escalate when the
dialog is actively painful (scrolls too tall, can't fit tabs, makes
mobile unusable).

## Routes

Two new routes per entity, both permission-guarded:

```ts
// router.tsx
const customerNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/customers/new',
  component: CustomerEditPage,
  beforeLoad: createPermissionGuard('Ibl360.Customers.Create'),
})

const customerEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/customers/$id/edit',
  component: CustomerEditPage,
  beforeLoad: createPermissionGuard('Ibl360.Customers.Edit'),
})
```

The **same component** serves both routes. It reads `useParams().id`;
if undefined → create mode, if defined → fetch + edit mode. The list
page navigates with `<Link to="/customers/new">` or
`navigate({ to: '/customers/$id/edit' })`.

## List page changes

The list page LOSES the inline `<Dialog>` form. Instead:

- "New" button is an `<a>` / `<Link>` to `/{plural}/new`.
- Row click navigates to `/{plural}/$id/edit` (set `cursor-pointer`
  on the row, `onClick={(e) => e.stopPropagation()}` on the cell that
  hosts the RowMenu so the dropdown still works).
- Edit action in RowMenu also navigates.
- Mobile FAB becomes an `<a>` to `/new`.

## The shell

Centralise the chrome in a single component so every entity that takes
this path looks identical and ships with the same a11y and responsive
guarantees out of the box.

Location: `react/src/components/business-party/EditPageShell.tsx`
(or wherever your shared editor namespace lives — keep one place).

Responsibilities:

1. **Sticky header** with `backdrop-blur supports-[backdrop-filter]:bg-…/70`,
   back button (icon only `<sm`, icon + label on `sm+`), truncating title,
   `Cancel` + `Save` actions on `lg+`.
2. **Mobile bottom action bar**: `fixed inset-x-0 bottom-0 z-30 lg:hidden`
   with the same Cancel/Save. Pads with
   `pb-[max(0.75rem,env(safe-area-inset-bottom))]` so iOS home indicator
   doesn't sit on top of the buttons.
3. **Tabs slot**: accepts a `tabs` prop, renders it inside a `<Card>`
   above the form body.
4. The submit button uses `form="..."` so it can live OUTSIDE the
   `<form>` tag and still trigger react-hook-form's `handleSubmit`.

Page wraps its form like this:

```tsx
return (
  <EditPageShell
    title={title}
    backTo="/customers"
    formId="customer-form"
    saving={createMutation.isPending || updateMutation.isPending}
    onCancel={() => navigate({ to: '/customers' })}
    tabs={<TabsStrip tabs={TABS} active={tab} onChange={setTab} errorTabs={tabsWithErrors} />}
  >
    <form id="customer-form" onSubmit={form.handleSubmit(onSubmit)}>
      <CardContent className="p-4 sm:p-5">
        {tab === 'general' && <GeneralPanel form={form} />}
        {/* ... */}
      </CardContent>
    </form>
  </EditPageShell>
)
```

Remember `pb-24 lg:pb-0` on the outer container of the page (or on the
shell itself, as in IBL360) to leave room for the fixed mobile bar.

## Tabs

A simple `TabsStrip<K extends string>` generic component:

- `flex gap-1 overflow-x-auto px-3 pt-3` for horizontal scroll on mobile.
- **Left + right gradient fades** as `pointer-events-none absolute`
  pseudo-blocks, `lg:hidden`. Users on phones see the hint that more
  tabs exist; on desktop the strip fits.
- Each tab is a `<button role="tab" aria-selected={isActive}>` with
  focus-visible ring (`focus-visible:ring-2 focus-visible:ring-primary/40
  focus-visible:ring-offset-1`).
- Decorate tabs with a small red dot when their fields have validation
  errors: compute `errorTabs: Set<TabKey>` from `form.formState.errors`
  via a mapping `{ tabKey: [fieldName, ...] }`. The user can't miss an
  error that landed on a different tab.

The full implementation is in
`react/src/components/business-party/EditPageShell.tsx`. Copy it
verbatim for a new project; tweak `from-bg-base` if your page bg differs.

## Reusable field-group components

The biggest payoff of the dedicated-page pattern is that you can extract
field groups and reuse them across entities. Keep them in
`components/business-party/` (or rename to your bounded context).

Templates from IBL360, all five are battle-tested:

### PostalAddressFields

Headless wrt the form library. Caller passes `register` (from
`useForm`) and `prefix` (e.g. `"billingAddress"` or
`"shippingAddresses.0"`). Renders the 5 address inputs with proper
grid layout (`sm:grid-cols-[1fr_140px]` for city + ZIP). One component
drives billing, all shipping addresses, and any future address slot
(legal, branch office, …).

### SocialsEditor

A `useFieldArray` list of `{platform: SocialPlatform, url: string}`.
Platform is a **closed enum** with a per-value metadata table
(icon from lucide-react, placeholder URL, brand color). The icon
shows up in both the Select trigger AND in each SelectItem.

**Three known traps**, all fixed in the IBL360 version, all worth a
mention here so the next implementer doesn't repeat them:

1. **Trigger double-icon**: shadcn `<SelectValue />` echoes the
   children of the selected `<SelectItem>` (which include the icon).
   If you also render an icon in the trigger, you get TWO icons.
   Solution: don't use `<SelectValue />` in the trigger; render
   icon + label explicitly via a lookup.

2. **Icon-stacked-over-label**: shadcn `SelectTrigger` has
   `[&>span]:line-clamp-1` baked in. Any direct `<span>` child gets
   `display: -webkit-box` applied, which stacks its children
   vertically. Workaround: use `<div>` as the inner wrapper instead
   of `<span>`.

3. **Grid `[180px | 1fr | auto]` blows up on mobile**: the URL field
   collapses to "https://x.". Use a responsive grid:
   `grid-cols-[1fr_auto] sm:grid-cols-[180px_1fr_auto]` with the Select
   `col-span-2 sm:col-auto`. Tap target on the X button stays at
   `h-10 w-10`.

### ShippingAddressesEditor

The trickiest of the five. Combines:

- `ShippingSameAsBilling: bool` checkbox.
- `ShippingAddresses: PostalAddress[]` list (each with its own `Id`).
- `DefaultShippingAddressId: Guid?` pointer **on the parent**, not on
  each address. Toggling the default flips the pointer; deleting the
  current default promotes the next item.

**Don't nest cards.** Each shipping address is a row in a `<ul>`
separated by `border-t border-border-hairline`, with the current
default getting a `bg-success/5` row tint (not a side stripe — the
shared design law forbids border-left accents).

Backend pairing: the entity needs a `NormalizeShippingState()` method
called by the AppService on every Create/Update. It clears the list
when SameAsBilling is true, drops empty rows, and ensures the default
points to an actual list member or null. See abp-feature-dev
`references/business-party.md` for the C# pattern.

### CommPrefsEditor

A two-checkbox block (`DoNotEmail`, `DoNotBulkEmail`). Trivial, but
**use a styled Checkbox primitive**, not native `<input
type="checkbox">`. The IBL360 project ships
`components/ui/checkbox.tsx` — a headless wrapper around a native
input with a visible peer-checked square and focus ring. Add it to
any project that doesn't have one before building this kind of form.

### CustomFieldsEditor

Same structure as SocialsEditor but with two text inputs (key + value)
instead of a Select + URL. Same responsive trap: use the same
responsive grid pattern. Same tap-target rule on the trash button.

## A11y baseline

The shell + components ship these for free; verify nothing slipped:

- Sticky header + tab strip both keyboard-reachable.
- TabsStrip uses `role="tablist"`, each tab `role="tab"` +
  `aria-selected`.
- "Set as default" button on shipping rows uses
  `aria-pressed={isDefault}` and `disabled={isDefault}` (so the user
  can't re-promote the already-default row).
- Every editable list row has an `aria-label` on its remove button
  (`AbpUi::Delete` — already in the bundle).
- Checkbox primitive forwards focus to the underlying native input;
  `Space` toggles, `Tab` moves on.

## Mobile traps to grep for before merging

Run these checks on the page after wiring it up. They map to actual
bugs that have shipped in IBL360 and were caught by `impeccable`:

| Search | Why it's a smell |
|---|---|
| `grid-cols-\[\d+px_` | A fixed-px first column without a `sm:grid-cols-…` override blows up the row on <500px |
| `<input type="checkbox"` | Use the project Checkbox primitive |
| `h-8 w-8` on a Button next to an Input | Tap target too small; `h-10 w-10` is the floor |
| `overflow-x-auto` without a sibling fade `bg-gradient-to-…` | Tab/list strip with no overflow hint |
| `<Dialog>` in an edit page | You picked the wrong pattern; dialogs belong to the list page |
| `border border-… p-4` inside another `border border-… p-4` | Nested cards — replace inner with row dividers |
| Action bar at the page top with no `sticky` or fixed mobile counterpart | Save button scrolls away |

## Final pass

Run `impeccable` on the new files (see SKILL.md Step 7). The skill has
seen these patterns and catches the trio above plus a11y / focus /
visual-hierarchy issues that a quick read won't.
