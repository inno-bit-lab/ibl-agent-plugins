# Shared components inventory

The Ibl360 React app ships a small, opinionated set of UI primitives and
helpers. **Reuse them on every new page** — don't roll your own buttons,
cards, dialogs, status pills, or tooltip primitives. Inconsistency here
is the #1 way the product starts to feel sloppy.

Mental model: this list is the **standard library**. If the answer to "how
do I build X" lives here, use what's here. If it doesn't, talk to the
design system owner before inventing.

## Brand

### `<ProductLogo>` and `<ProductMark>`
File: `src/components/brand/Logo.tsx`

`ProductLogo` = mark + wordmark ("Ibl360" with the "360" in `--primary`).
`ProductMark` = just the square "i in a blue box" mark.

```tsx
import { ProductLogo, ProductMark } from '@/components/brand/Logo'

<ProductLogo size="sm" />              // sidebar header (expanded)
<ProductMark  size="sm" />             // sidebar header (collapsed)
<ProductLogo size="md" showTagline />  // login splash
```

Sizes: `xs / sm / md / lg / xl`. Sizes are pixel-tuned (not relative) so
the mark always reads as the same affordance regardless of context.

### `<InnobitLabLogo>`
File: `src/components/brand/Logo.tsx`

The company wordmark — bicromatic SVG (`#5382A1` + `#F89820`). Lives in
`public/brand/innobitlab-wordmark.svg`. **Never recolor or restyle.**

```tsx
import { InnobitLabLogo } from '@/components/brand/Logo'

<InnobitLabLogo variant="wordmark" height={20} />   // footer "Powered by"
<InnobitLabLogo variant="mark"     height={28} />   // bare arrow-glyph
```

## Layout primitives (rarely instantiated, but good to know)

| Component | File | Use |
|---|---|---|
| `<AppLayout>` | `components/layout/AppLayout.tsx` | The shell — sidebar + header + main + footer. Only the router renders this. |
| `<Sidebar>` | `components/layout/Sidebar.tsx` | Driven by `routeConfig`. To add a nav item, edit `lib/routing/route-config.ts`. |
| `<Header>` | `components/layout/Header.tsx` | Top bar with page title + tenant switch + language + theme + bell + help + user menu. |
| `<TenantSwitch>` | `components/layout/TenantSwitch.tsx` | Chip in the header that opens a tenant-resolution dialog. |
| `<UserMenu>` | `components/layout/UserMenu.tsx` | Avatar + name + dropdown with account actions. |
| `<AccountLayout>` | `components/layout/AccountLayout.tsx` | Brand-panel + form-panel split for login/register/forgot/reset. |

99% of new feature work doesn't touch any of these — you write a Page
component, register it as a route, and these wrap it for free.

## UI primitives

### `<Button>`
File: `src/components/ui/button.tsx` (re-exported as `@/components/ui/button`)

All buttons are pill (`rounded-full`). Variants:

| Variant | Use |
|---|---|
| `default` | Primary action — blue fill. The most common one. |
| `accent` | THE moment of action per screen — orange gradient, shadow. Use ONCE per screen. Examples: top-of-page "+ Nuovo cliente", lifecycle CTAs, mobile FAB. |
| `secondary` | Outline-style — white with primary text and a hairline border. Inline alternates to primary. |
| `ghost` | Transparent — for toolbar buttons, "Cancel" in dialogs, ghost actions in dropdowns. |
| `destructive` | Ghost in `--error` color. We do NOT ship a filled red button. |
| `link` | Inline text link in `--primary`. |

Sizes: `sm` (h-8) · `default` (h-10) · `lg` (h-11) · `icon` (40×40) · `icon-sm` (32×32).

```tsx
<Button>{t('Save')}</Button>                                  // default
<Button variant="accent"><Plus className="size-4" /> Nuovo</Button>
<Button variant="ghost" size="icon-sm" aria-label="Menu">
  <Menu className="size-5" />
</Button>
<Button asChild><Link to="/foo">Go</Link></Button>             // wrap a Link
```

### `<Card>` family
File: `src/components/ui/card.tsx`

White bg, `rounded-2xl`, `--shadow-card`, no border. Compose with header/content/footer
slots — never wrap with raw padding.

```tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'

<Card>
  <CardHeader>
    <CardTitle>Andamento clienti</CardTitle>
    <CardDescription>Ultimi 30 giorni</CardDescription>
  </CardHeader>
  <CardContent>{/* chart / table / form */}</CardContent>
</Card>
```

For KPI tiles (smaller cards used in a grid), pass `className="px-5 py-4"`
to override the default padding.

### `<Input>` and `<Label>`
Files: `src/components/ui/input.tsx`, `src/components/ui/label.tsx`

Filled style (sits on `bg-elev`), no border by default. On focus the
background lifts to `bg-card` AND gains a `primary-soft` ring. 40px tall
to align with Button sizes. For most form fields you don't instantiate
Label directly — reach for `<Field>` instead (below).

### `<Field>` — labelled form field
File: `src/components/ui/field.tsx`

The canonical wrapper for a labelled control with optional required
asterisk and inline error. **Use this on every form field.** Don't
redeclare a local `Field` helper at the bottom of the page — we already
shipped six copies of that pattern and consolidated them here.

```tsx
import { Field } from '@/components/ui/field'

<Field
  label={t('LegalName', 'Ragione sociale')}
  required
  error={form.formState.errors.legalName?.message}
>
  <Input {...form.register('legalName')} />
</Field>

// Without required, without an error binding:
<Field label={t('Phone', 'Telefono')}>
  <Input {...form.register('phone')} />
</Field>
```

Renders: the label in the small-caps treatment
(`uppercase tracking-[0.06em] text-fg-muted`), an `*` in `text-error`
after the label when `required`, the children (your control), and an
inline `<p className="text-xs text-error">` for the error when present.

`className` is forwarded to the wrapping `<div className="grid
gap-1.5">` for the rare layout adjustment.

For non-form labels (a section heading, a hint group, a date picker
with a help line beneath) reach for `Label` directly — `<Field>` is
specifically the form-field wrapper.

### `<Select>` (shadcn)
File: `src/components/ui/select.tsx`

Standard Radix-based select. To make the trigger match Input's filled style:
`className="h-10 bg-bg-elev border-0"`.

For filter chips on toolbars: also add `rounded-full w-[160px]`.

### `<Dialog>` family
File: `src/components/ui/dialog.tsx`

Backdrop is a tinted-dim with backdrop-blur (not pure black). Panel is
`bg-card`, `rounded-2xl`, `--shadow-dialog`. ESC closes; body scroll locks
when open. The close X icon-button is added automatically (pass
`hideClose` to suppress).

```tsx
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogBody, DialogFooter,
} from '@/components/ui/dialog'

<Dialog open={open} onOpenChange={setOpen}>
  <DialogContent className="max-w-[480px]">
    <DialogHeader>
      <DialogTitle>{t('Customers:EditTitle')}</DialogTitle>
      <DialogDescription>{t('Some helper text')}</DialogDescription>
    </DialogHeader>
    <DialogBody>{/* form fields */}</DialogBody>
    <DialogFooter>
      <Button variant="ghost" onClick={() => setOpen(false)}>Annulla</Button>
      <Button onClick={onSave}>Salva</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

### `<ConfirmDialog>`
File: `src/components/ui/confirm-dialog.tsx`

Pre-composed dialog for "are you sure" flows. Pass `variant="destructive"`
to render the confirm button in ghost-red.

```tsx
<ConfirmDialog
  open={confirmId !== null}
  onOpenChange={(open) => !open && setConfirmId(null)}
  title={t('Customers:DeleteTitle', { name: customer.legalName })}
  description={t('Customers:DeleteDescription')}
  variant="destructive"
  confirmLabel={t('AbpUi::Delete')}
  cancelLabel={t('AbpUi::Cancel')}
  onConfirm={() => deleteMutation.mutate(confirmId!)}
  isPending={deleteMutation.isPending}
/>
```

### `<Table>` family + `<StatusPill>`
File: `src/components/ui/table.tsx`

Sticky header on `--bg-elev`, no row borders, hover swaps to `--bg-row-hover`.
Header has a hairline at the bottom (added automatically by `<TableHead>`).

```tsx
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell, StatusPill,
} from '@/components/ui/table'

<Table>
  <TableHeader>
    <TableRow>
      <TableHead className="w-[44px]"></TableHead>
      <TableHead>{t('LegalName')}</TableHead>
      <TableHead>{t('Status')}</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {items.map((c) => (
      <TableRow key={c.id}>
        <TableCell>{/* dropdown trigger */}</TableCell>
        <TableCell className="font-medium text-fg-strong">{c.legalName}</TableCell>
        <TableCell>
          <StatusPill tone="success">{t(`Enum:CustomerStatus.${c.status}`)}</StatusPill>
        </TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

`<StatusPill tone="…">` tones: `success / info / warning / error / muted`.
Renders as `● Label` — colored dot + text in the same color, on a 10%
opacity background. Maps domain enums → tones in the page (e.g. `Prospect → info`,
`Active → success`, `Churned → muted`).

**Responsive note:** tables only render at `lg` (≥1024px). For mobile +
tablet, render a card-list instead — see `page-pattern.md`.

### `<DropdownMenu>` family (shadcn)
File: `src/components/ui/dropdown-menu.tsx`

Standard. Use for row action menus (the `MoreVertical` trigger in tables)
and for the user menu / language menu in the header.

### `<DatePicker>`
File: `src/components/ui/date-picker.tsx`

Trigger looks like a filled Input. Value/onChange are ISO date strings
(`YYYY-MM-DD`). Wrap in a `<Controller>` for use with react-hook-form.

### `<Popover>` (shadcn) / `<Calendar>`
Files: `src/components/ui/popover.tsx`, `src/components/ui/calendar.tsx`

Building blocks for date-picker and other contextual surfaces. Rarely
instantiated directly.

### `Toaster` (sonner)
File: `src/components/ui/sonner.tsx`

Mounted once in `<App>`. Call `toast.success(...)`, `toast.error(...)`
from anywhere.

```tsx
import { toast } from 'sonner'

toast.success(t('AbpUi::SavedSuccessfully'))
toast.error(t('AbpUi::Error'))
```

## Tooltips for sidebar rail

### `<RailTooltip>`
File: `src/components/layout/RailTooltip.tsx`

Portal-based tooltip that shows on hover/focus of the wrapped child. Used
ONLY by the sidebar when the rail is collapsed. Pass `label=undefined` to
render the child without any wrapping behavior.

```tsx
<RailTooltip label={collapsed ? 'Clienti' : undefined}>
  <Link to="/customers" className="…">…</Link>
</RailTooltip>
```

For tooltips ELSEWHERE in the app (table column header, info hint, etc.)
you don't need RailTooltip — use the native `title` attribute or the
shadcn `<Tooltip>` if you add one. RailTooltip is rail-specific.

## Hooks

### `useDebouncedSearch`
File: `src/hooks/useDebouncedSearch.ts`

Debounced server-side search with minimum-length gate. **Mandatory for any
text filter that hits the backend** — otherwise you fire a request per
keystroke and waste bandwidth.

```tsx
import {
  useDebouncedSearch,
  SEARCH_MIN_CHARS,    // default 2
  SEARCH_DEBOUNCE_MS,  // default 350
} from '@/hooks/useDebouncedSearch'

const [filter, setFilter] = useState('')
const { effective: effectiveFilter, status: searchStatus } = useDebouncedSearch(filter)

const { data, isFetching } = useQuery({
  queryKey: ['customers', effectiveFilter, /* …other filters… */],
  queryFn: () => getCustomers({ filter: effectiveFilter || undefined, /* … */ }),
})

// In the input area:
<Input value={filter} onChange={(e) => setFilter(e.target.value)} className="pl-10 pr-10" />
{(searchStatus === 'typing' || (searchStatus === 'searching' && isFetching)) && (
  <span className="absolute right-3 top-1/2 size-3.5 -translate-y-1/2 animate-spin
                   rounded-full border-2 border-fg-muted border-t-transparent" />
)}
{searchStatus === 'too-short' && (
  <p className="mt-1 text-[11px] text-fg-faint">
    {t('Search:MinChars', { n: SEARCH_MIN_CHARS })}
  </p>
)}
```

`status` values: `idle | typing | too-short | searching`. See
`page-pattern.md` for the full filter-bar example.

### `useDebouncedValue<T>`
Same file. Lower-level primitive — debounces ANY value, no min-length
gate. Use only if you have a specific non-search debounce need.

## Permissions & auth helpers

### `usePermissions()`
File: `src/lib/auth/permissions.ts`

```tsx
const { isGranted } = usePermissions()
const canEdit   = isGranted('Ibl360.Customers.Edit')
const canDelete = isGranted('Ibl360.Customers.Delete')
```

Permission strings come from the backend `Ibl360Permissions.*` constants.
Use them on buttons (`canEdit && <Button>…</Button>`) and on conditional
menu items inside dropdowns. Route-level guarding is via
`createPermissionGuard('Ibl360.Customers')` in the router.

### `useCurrentUser()`
Returns the snapshot of the current user (id, userName, name, email).

### `useAuth()`
Returns `{ user, isAuthenticated, isLoading, login, logout, getAccessToken, navigateToLogin }`.

## Routing helpers

### `createPermissionGuard`
File: `src/lib/routing/guards.ts`

```tsx
const customersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/customers',
  component: CustomersPage,
  beforeLoad: createPermissionGuard('Ibl360.Customers'),
})
```

### `authGuard`
Same file. Use when you only need "is the user logged in" without a
specific permission.

## What's intentionally NOT in the standard library

These are commonly-asked-for but deliberately absent:

| Asked for | Use instead |
|---|---|
| `<Spinner>` / `<Loader>` | Skeleton blocks inside the card layout (see CustomersPage `TableSkeleton`). Spinners only inside Buttons when a mutation is in flight. |
| `<Badge>` for status | `<StatusPill>` — same idea, brand-coherent. |
| `<Alert>` for errors | Inline `<p className="text-xs text-error">…</p>` next to the field. For toasts use `toast.error()`. |
| `<Tabs>` | Shadcn's Tabs is installable but isn't currently used. Add ONLY if a real need surfaces — most "tabs" requests are better solved with section headings + a card grid. |
| `<Avatar>` | Build inline: `<span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-primary text-fg-on-primary text-xs font-semibold">MR</span>` (see UserMenu). |

Reach for "make it match the existing patterns" before reaching for a new
primitive. Consistency >> feature surface area.
