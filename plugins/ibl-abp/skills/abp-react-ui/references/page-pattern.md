# CRUD page pattern

One page file at `react/src/pages/{plural}/{Entity}Page.tsx`. Standard
layout: subtitle + "New" button row, filter bar, paginated table
(desktop) / card-list (mobile + tablet), create/edit dialog with RHF+Zod
form, delete confirmation, optional lifecycle actions, mobile FAB.

## Don't repeat the page title

The AppShell's top bar **already displays the page title** (derived from
the active route's `nameKey` in `route-config.ts`). Adding an `<h1>` with
the same word right below is redundant — wasted vertical space and a
"title triplo" smell.

**Right** (Clienti page):

```tsx
{/* Top bar says "Clienti" already. We just need the contextual subtitle. */}
<div className="flex flex-wrap items-center justify-between gap-3">
  <p className="text-sm text-fg-muted">
    {t('Customers:Header.Count', { count: totalCount })}
  </p>
  {canCreate && <Button variant="accent" onClick={openCreate}>+ Nuovo cliente</Button>}
</div>
```

**Wrong**:

```tsx
<div className="flex flex-wrap items-end justify-between gap-3">
  <div>
    <h1 className="text-3xl font-semibold">{t('Menu:Customers')}</h1>  {/* DUPLICATE — top bar already has this */}
    <p className="mt-1 text-sm text-fg-muted">{t('Customers:Header.Count', { count })}</p>
  </div>
  {canCreate && <Button>+ Nuovo cliente</Button>}
</div>
```

**When IS an `<h1>` justified?** When it says something different from
the topbar — a greeting, a contextual subtitle, the entity name on a
detail page. Examples:

- HomePage topbar says "Home", H1 says **"Buongiorno, Marco"** (greeting,
  contextual to the user)
- Detail page topbar says "Clienti", H1 says **"Acme S.p.A."** (the
  specific record)
- Multi-tab page topbar says "Progetti", H1 says **"Contratti"** (the
  active sub-section)

The rule: **the H1 must add information the topbar can't carry.** If
it's the same word, drop it.

> **Read first:**
> - `shared-components.md` — every primitive used here (`<Button>`,
>   `<Card>`, `<Table>`, `<StatusPill>`, `<Dialog>`, `<ConfirmDialog>`,
>   `useDebouncedSearch`)
> - `data-fetching.md` — the TanStack Query + mutations + permissions
>   wiring
> - `design-tokens.md` — the color / radius / shadow utility classes
>   referenced below (`bg-accent`, `text-fg-strong`, etc.)
>
> This file is the **page composition recipe**: how the primitives
> assemble together. It does NOT redefine them.

## Shape

```
┌──────────────────────────────────────────────────┐
│  {Entities}                       [+ New {Entity}]│   ← header (permission-gated button)
├──────────────────────────────────────────────────┤
│  [search]  [status ▾]  [segment ▾]                │   ← filter bar
│                                                   │
│  ┌─────┬────────┬────────┬──────┬──────┬──────┐  │
│  │ ⋮   │ Field1 │ Field2 │ Enum │ Date │ ...  │  │   ← table with actions column
│  └─────┴────────┴────────┴──────┴──────┴──────┘  │
│                                                   │
│  [< Prev]      Page 1 / 5      [Next >]          │   ← pagination
└──────────────────────────────────────────────────┘
```

Action menu (per row): Edit, [lifecycle transitions], Delete (destructive).

## Template

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Controller, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { usePermissions } from '@/lib/auth/permissions'
import {
  get{Entities}, create{Entity}, update{Entity}, delete{Entity},
  change{Entity}Status,            // omit if no lifecycle
  {entity}SegmentOptions,
  {entity}StatusOptions,
  type {Entity}Dto,
  type CreateUpdate{Entity}Dto,
  type {Entity}Status,
  type {Entity}Segment,
} from '@/lib/api/{entityCamel}'

// Zod schema mirrors the C# CreateUpdateDto + its DataAnnotations.
// Keep .max() / .length() in sync with the [StringLength] attributes.
const {entityCamel}Schema = z.object({
  legalName:   z.string().min(1, 'Required').max(256),
  displayName: z.string().min(1, 'Required').max(128),
  taxId:       z.string().max(64).optional().or(z.literal('')),
  // For exact-length-when-present fields:
  fiscalCode:  z.string().length(16, '16 chars').optional().or(z.literal('')),
  address:     z.string().max(512).optional().or(z.literal('')),
  country:     z.string().length(2, '2 chars'),
  segment:     z.enum(['Smb', 'Enterprise', 'Public']),
})

type {Entity}FormData = z.infer<typeof {entityCamel}Schema>

const PAGE_SIZE = 10

export function {Entity}Page() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { isGranted } = usePermissions()
  // One canCreate / canEdit / canDelete per permission constant.
  const canCreate = isGranted('{RootNs}.{Plural}.Create')
  const canEdit   = isGranted('{RootNs}.{Plural}.Edit')
  const canDelete = isGranted('{RootNs}.{Plural}.Delete')

  // Filter state — one piece of useState per filter.
  // 'all' sentinel for nullable enum filters; mapped to undefined in the query.
  const [filter, setFilter]               = useState('')
  const [statusFilter, setStatusFilter]   = useState<{Entity}Status | 'all'>('all')
  const [segmentFilter, setSegmentFilter] = useState<{Entity}Segment | 'all'>('all')
  const [skipCount, setSkipCount]         = useState(0)
  const [editing, setEditing]             = useState<{Entity}Dto | null>(null)
  const [isFormOpen, setIsFormOpen]       = useState(false)
  const [confirmId, setConfirmId]         = useState<string | null>(null)

  // Query key includes every filter so React Query refetches automatically.
  const { data, isLoading } = useQuery({
    queryKey: ['{plural-kebab}', filter, statusFilter, segmentFilter, skipCount],
    queryFn: () =>
      get{Entities}({
        filter:  filter || undefined,
        status:  statusFilter  === 'all' ? undefined : statusFilter,
        segment: segmentFilter === 'all' ? undefined : segmentFilter,
        skipCount,
        maxResultCount: PAGE_SIZE,
        sorting: 'creationTime desc',
      }),
  })

  // One mutation per write. Always invalidateQueries on success.
  const createMutation = useMutation({
    mutationFn: create{Entity},
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['{plural-kebab}'] })
      setIsFormOpen(false)
      toast.success(t('AbpUi::SavedSuccessfully'))
    },
    onError: () => toast.error(t('AbpUi::Error')),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: string; input: CreateUpdate{Entity}Dto }) =>
      update{Entity}(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['{plural-kebab}'] })
      setIsFormOpen(false)
      setEditing(null)
      toast.success(t('AbpUi::SavedSuccessfully'))
    },
    onError: () => toast.error(t('AbpUi::Error')),
  })

  const deleteMutation = useMutation({
    mutationFn: delete{Entity},
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['{plural-kebab}'] })
      toast.success(t('AbpUi::DeletedSuccessfully'))
    },
    onError: () => toast.error(t('AbpUi::Error')),
  })

  // Lifecycle mutation: special error handling because the backend throws
  // BusinessException with a localized message that the user should see verbatim.
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: {Entity}Status }) =>
      change{Entity}Status(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['{plural-kebab}'] })
      toast.success(t('AbpUi::SavedSuccessfully'))
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { error?: { message?: string } } } }
      toast.error(e?.response?.data?.error?.message ?? t('AbpUi::Error'))
    },
  })

  const form = useForm<{Entity}FormData>({
    resolver: zodResolver({entityCamel}Schema),
    defaultValues: { /* one per field, matches the schema */ },
  })

  const openCreate = () => {
    setEditing(null)
    form.reset({ /* same defaults */ })
    setIsFormOpen(true)
  }

  const openEdit = (c: {Entity}Dto) => {
    setEditing(c)
    form.reset({
      legalName:   c.legalName,
      displayName: c.displayName,
      taxId:       c.taxId ?? '',         // optional fields: nullable → empty string
      fiscalCode:  c.fiscalCode ?? '',
      address:     c.address ?? '',
      country:     c.country,
      segment:     c.segment,
    })
    setIsFormOpen(true)
  }

  const onSubmit = (values: {Entity}FormData) => {
    const input: CreateUpdate{Entity}Dto = {
      legalName:   values.legalName,
      displayName: values.displayName,
      taxId:       values.taxId || null,     // empty string → null on the wire
      fiscalCode:  values.fiscalCode || null,
      address:     values.address || null,
      country:     values.country.toUpperCase(),
      segment:     values.segment,
    }
    if (editing) {
      updateMutation.mutate({ id: editing.id, input })
    } else {
      createMutation.mutate(input)
    }
  }

  const totalCount  = data?.totalCount ?? 0
  const totalPages  = Math.ceil(totalCount / PAGE_SIZE)
  const currentPage = Math.floor(skipCount / PAGE_SIZE) + 1

  return (
    <div className="space-y-6">
      {/* Header: localized title + permission-gated New button */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">{t('{Plural}')}</h1>
        {canCreate && <Button onClick={openCreate}>{t('New{Entity}')}</Button>}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('{Plural}')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filter bar — one widget per filter, always reset skipCount on change */}
          <div className="flex flex-wrap gap-3">
            <Input
              placeholder={t('AbpUi::Search', 'Search')}
              value={filter}
              onChange={(e) => { setFilter(e.target.value); setSkipCount(0) }}
              className="max-w-xs"
            />
            <Select
              value={statusFilter}
              onValueChange={(v) => { setStatusFilter(v as {Entity}Status | 'all'); setSkipCount(0) }}
            >
              <SelectTrigger className="w-44"><SelectValue placeholder={t('Status')} /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('::All', 'All')}</SelectItem>
                {{entityCamel}StatusOptions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{t(o.key)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {/* ... one Select per enum filter ... */}
          </div>

          {isLoading ? (
            <p className="text-muted-foreground">{t('AbpAccount::PleaseWait')}</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[120px]">{t('AbpIdentity::Actions')}</TableHead>
                    <TableHead>{t('LegalName')}</TableHead>
                    {/* one TableHead per column */}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(data?.items ?? []).map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm">
                              {t('AbpUi::Actions')} <ChevronDown className="ml-1 h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {canEdit && (
                              <DropdownMenuItem onClick={() => openEdit(c)}>
                                {t('AbpUi::Edit')}
                              </DropdownMenuItem>
                            )}
                            {/* Lifecycle action items: show only the transitions allowed from
                                the current status. The backend will still validate, but hiding
                                disallowed actions matches user expectations. */}
                            {canEdit && c.status === 'Prospect' && (
                              <DropdownMenuItem
                                onClick={() => statusMutation.mutate({ id: c.id, status: 'Active' })}
                              >
                                {t('ChangeStatus')}: {t('Enum:{Entity}Status.Active')}
                              </DropdownMenuItem>
                            )}
                            {canDelete && (
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() => setConfirmId(c.id)}
                              >
                                {t('AbpUi::Delete')}
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                      <TableCell>{c.legalName}</TableCell>
                      {/* one TableCell per column. For enums, look up the i18n key:
                          t(`Enum:{Entity}Status.${c.status}`) — works because the
                          key is name-based (Enum:CustomerStatus.Active, not .1). */}
                      <TableCell>{t(`Enum:{Entity}Status.${c.status}`)}</TableCell>
                    </TableRow>
                  ))}
                  {(data?.items?.length ?? 0) === 0 && (
                    <TableRow>
                      <TableCell colSpan={N} className="text-center text-muted-foreground">
                        {t('::NoData', 'No data')}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {/* Pagination only shown if needed */}
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <Button variant="outline" size="sm"
                          disabled={skipCount === 0}
                          onClick={() => setSkipCount((s) => Math.max(0, s - PAGE_SIZE))}>
                    {t('AbpUi::PagerPrevious', 'Previous')}
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    {currentPage} / {totalPages}
                  </span>
                  <Button variant="outline" size="sm"
                          disabled={skipCount + PAGE_SIZE >= totalCount}
                          onClick={() => setSkipCount((s) => s + PAGE_SIZE)}>
                    {t('AbpUi::PagerNext', 'Next')}
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmId !== null}
        onOpenChange={(open) => !open && setConfirmId(null)}
        title={t('::AreYouSureToDelete')}
        variant="destructive"
        confirmLabel={t('AbpUi::Delete')}
        cancelLabel={t('AbpUi::Cancel')}
        onConfirm={() => {
          if (confirmId) deleteMutation.mutate(confirmId)
          setConfirmId(null)
        }}
        isPending={deleteMutation.isPending}
      />

      {/* Create / Edit dialog. Same form for both — distinguish by editing != null. */}
      <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
        <DialogContent className="max-w-lg">
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>
                {editing ? t('AbpIdentity::Edit') : t('New{Entity}')}
              </DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              {/* One <Field> per form input. Two-column for paired short fields. */}
              <Field label={t('LegalName')} error={form.formState.errors.legalName?.message}>
                <Input {...form.register('legalName')} />
              </Field>
              {/* ... */}
              <Field label={t('Segment')} error={form.formState.errors.segment?.message}>
                <Controller
                  name="segment"
                  control={form.control}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {{entityCamel}SegmentOptions.map((o) => (
                          <SelectItem key={o.value} value={o.value}>{t(o.key)}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </Field>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsFormOpen(false)}>
                {t('AbpUi::Cancel')}
              </Button>
              <Button type="submit"
                      disabled={createMutation.isPending || updateMutation.isPending}>
                {t('AbpAccount::Save')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// Small helper at the bottom of the file — keeps form markup terse.
function Field({
  label, error, children,
}: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
```

## Responsive switch — table ↔ card-list

Tables overflow horizontally below ~1024px. The standard pattern:

```tsx
{/* table — desktop only (≥ lg) */}
<Card className="hidden lg:block overflow-hidden">
  <CardContent className="p-0">
    {/* <Table>…</Table> */}
  </CardContent>
</Card>

{/* card list — mobile + tablet (< lg) */}
<div className="lg:hidden space-y-2">
  {items.map((c) => (
    <Card key={c.id} className="px-4 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-medium text-fg-strong truncate">{c.legalName}</div>
          <div className="text-xs text-fg-muted truncate">{c.displayName}</div>
          <div className="mt-2"><StatusPill tone="success">…</StatusPill></div>
        </div>
        {/* the same row-action dropdown */}
      </div>
    </Card>
  ))}
</div>
```

Both render from the SAME `items` array — there's only one query, one
data shape, one set of mutations. Just two presentations.

## Mobile FAB (primary action)

Below `lg`, replace the top-of-page "+ Nuovo" button with a floating
action button in the bottom-right corner:

```tsx
{canCreate && (
  <button
    type="button"
    onClick={openCreate}
    aria-label={t('NewCustomer')}
    className="fixed bottom-5 right-5 z-30 inline-flex h-14 w-14 items-center
               justify-center rounded-full bg-accent text-white
               shadow-[0_8px_24px_oklch(0.72_0.165_60/0.45)]
               transition-transform hover:scale-105 active:scale-100 lg:hidden"
  >
    <Plus className="size-6" strokeWidth={2.25} />
  </button>
)}
```

This is the **one moment of orange per screen** on mobile (see
`design-tokens.md` Restrained strategy). Reserve `bg-accent` for it.

Also remember to add `pb-20 lg:pb-0` on the page root so the FAB doesn't
cover the last list row.

## Search bar — debounced, gated, with feedback

```tsx
import { useDebouncedSearch, SEARCH_MIN_CHARS } from '@/hooks/useDebouncedSearch'

const [filter, setFilter] = useState('')
const { effective: effectiveFilter, status: searchStatus } = useDebouncedSearch(filter)

// In the toolbar:
<div className="relative flex-1 min-w-[200px]">
  <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4
                         -translate-y-1/2 text-fg-muted" />
  <Input
    placeholder={t('Customers:Search')}
    value={filter}
    onChange={(e) => { setFilter(e.target.value); setSkipCount(0) }}
    className="pl-10 pr-10"
  />
  {(searchStatus === 'typing' ||
    (searchStatus === 'searching' && isFetching)) && (
    <span aria-hidden
          className="absolute right-3 top-1/2 size-3.5 -translate-y-1/2
                     animate-spin rounded-full border-2 border-fg-muted
                     border-t-transparent" />
  )}
  {searchStatus === 'too-short' && (
    <p className="mt-1 text-[11px] text-fg-faint">
      {t('Search:MinChars', { n: SEARCH_MIN_CHARS })}
    </p>
  )}
</div>
```

See `shared-components.md` → `useDebouncedSearch` for the full hook API.

## Why this shape

- **Permission-gated buttons**, not just the route guard. A user with read
  but not Create still sees the list — the New button is hidden.
- **`'all'` sentinel** on enum filters because `<Select>` doesn't model
  "no value" well; mapping it to `undefined` keeps the API request clean.
- **`skipCount → 0` on every filter change** so changing a filter doesn't
  land the user on an empty page 5.
- **Query key contains all filters** so React Query refetches automatically
  without manual `refetch()` calls.
- **Empty-string ↔ null mapping** in `onSubmit` and `openEdit`. The wire
  format wants `null`, the form wants `''`. The translation is explicit at
  the boundary, not hidden inside Zod transforms.
- **Lifecycle actions filtered by current status** in the menu — UX hint
  that mirrors the backend's transition rules. The backend still validates.
- **Lifecycle error surfacing**: when the backend throws
  `BusinessException`, the localized message is in
  `error.response.data.error.message`. Surface it verbatim — it's already
  in the user's culture.
- **`isPending` on submit/delete buttons** prevents double-clicks during
  an in-flight request.

## Pieces to skip per situation

- **No filters** → drop the filter bar; still keep `queryKey` simple.
- **No lifecycle** → drop the status mutation and the conditional menu
  items.
- **Read-only feature** → drop create/update/delete mutations and the
  dialog. Use the same skeleton.
- **Embedded child entity** → no separate page; the parent page exposes
  the child editing UI inline.

## Files this references

For testing, place `{Entity}Page.test.tsx` alongside, mirroring the style
of `BooksPage.test.tsx`. Skip if the project doesn't have a test setup yet.
