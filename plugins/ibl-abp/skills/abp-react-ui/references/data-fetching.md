# Data fetching — backend → UI hand-off

Read this when an ABP AppService is freshly scaffolded (the "contract" is
ready) and you need to wire it into the React app. By the end of this
guide you'll know exactly which endpoint shape to call, how the tenant
header gets attached, how to plug TanStack Query in correctly, and how
filter/sort/paging defaults flow.

## What "contract ready" means

The backend scaffold (see `abp-feature-dev`) produced:

```
Services/{Plural}/I{Entity}AppService.cs        ← the contract
Services/{Plural}/{Entity}AppService.cs         ← the implementation
Services/Dtos/{Plural}/{Entity}Dto.cs           ← output shape
Services/Dtos/{Plural}/CreateUpdate{Entity}Dto.cs
Services/Dtos/{Plural}/Get{Entities}Input.cs    ← input shape (filters + paging)
Permissions/*Permissions.cs                     ← the gate names
```

ABP auto-generates a controller at `/api/app/{entity-kebab}` from the
AppService. Endpoints:

| HTTP | URL | Body / Query | Returns | Permission |
|---|---|---|---|---|
| GET | `/api/app/{entity}` | `Get{Entities}Input` as query string | `PagedResultDto<{Entity}Dto>` | `Ibl360.{Plural}` |
| GET | `/api/app/{entity}/{id}` | — | `{Entity}Dto` | `Ibl360.{Plural}` |
| POST | `/api/app/{entity}` | `CreateUpdate{Entity}Dto` JSON | `{Entity}Dto` | `Ibl360.{Plural}.Create` |
| PUT | `/api/app/{entity}/{id}` | `CreateUpdate{Entity}Dto` JSON | `{Entity}Dto` | `Ibl360.{Plural}.Edit` |
| DELETE | `/api/app/{entity}/{id}` | — | 204 | `Ibl360.{Plural}.Delete` |
| POST | `/api/app/{entity}/{id}/change-status` | `Change{Entity}StatusDto` JSON | `{Entity}Dto` (lifecycle only) | `Ibl360.{Plural}.Edit` |

Verify the actual URLs in `/swagger/v1/swagger.json` if uncertain — ABP's
pluralization isn't always what you'd guess (`/customer` vs `/customers`,
`/book` vs `/books`).

## Layer 1 — typed API client

One file per entity at `react/src/lib/api/{entityCamel}.ts`. The shared
`api` axios instance from `lib/api/axios.ts` already handles:

- **Bearer token** from the OIDC user manager
- **`__tenant` header** from sessionStorage (set by TenantSwitch; null
  means "host context")
- **`Accept-Language`** from current i18n culture
- **401 → login redirect**, **403 → `/403` redirect** (unless you pass
  `skipAuthRedirect: true` / `skip403Redirect: true` on the request)

So your per-entity module is **just types + endpoint paths**. Mirror the
backend DTOs one-to-one.

```ts
import { api } from './axios'

// Match C# enum NAMES — wire format is strings (JsonStringEnumConverter
// on the server) so TS types are string unions, not numeric enums.
export type CustomerStatus = 'Prospect' | 'Active' | 'Churned'
export type CustomerSegment = 'Smb' | 'Enterprise' | 'Public'

// Option arrays used by <Select> components.
// `key` is the name-based localization key (see `i18n.md`).
export const customerStatusOptions: { value: CustomerStatus; key: string }[] = [
  { value: 'Prospect', key: 'Enum:CustomerStatus.Prospect' },
  { value: 'Active',   key: 'Enum:CustomerStatus.Active' },
  { value: 'Churned',  key: 'Enum:CustomerStatus.Churned' },
]

export interface CustomerDto {
  id: string
  legalName: string
  // … one field per property in CustomerDto.cs
  segment: CustomerSegment
  status: CustomerStatus
  creationTime?: string
  lastModificationTime?: string | null
}

export interface CreateUpdateCustomerDto {
  legalName: string
  displayName: string
  // … one field per CreateUpdateCustomerDto.cs (no audit fields)
  segment: CustomerSegment
}

export interface GetCustomersInput {
  filter?: string
  status?: CustomerStatus
  segment?: CustomerSegment
  country?: string
  createdFrom?: string  // ISO date
  createdTo?: string
  maxResultCount?: number
  skipCount?: number
  sorting?: string      // e.g. "creationTime desc"
}

export interface PagedResultDto<T> { items: T[]; totalCount: number }

// Strip empty strings to undefined so axios doesn't send `?filter=` (which
// the backend treats as filter-on-empty-string).
export async function getCustomers(
  params: GetCustomersInput = {}
): Promise<PagedResultDto<CustomerDto>> {
  const { data } = await api.get<PagedResultDto<CustomerDto>>('/app/customer', {
    params: {
      filter:        params.filter || undefined,
      status:        params.status,
      segment:       params.segment,
      country:       params.country || undefined,
      createdFrom:   params.createdFrom || undefined,
      createdTo:     params.createdTo || undefined,
      maxResultCount: params.maxResultCount ?? 10,
      skipCount:      params.skipCount ?? 0,
      sorting:        params.sorting,
    },
  })
  return data
}

export async function createCustomer(input: CreateUpdateCustomerDto) {
  const { data } = await api.post<CustomerDto>('/app/customer', input)
  return data
}

export async function updateCustomer(id: string, input: CreateUpdateCustomerDto) {
  const { data } = await api.put<CustomerDto>(`/app/customer/${id}`, input)
  return data
}

export async function deleteCustomer(id: string): Promise<void> {
  await api.delete(`/app/customer/${id}`)
}

// Optional — only when the entity has a lifecycle method
export async function changeCustomerStatus(id: string, status: CustomerStatus) {
  const { data } = await api.post<CustomerDto>(
    `/app/customer/${id}/change-status`,
    { status }
  )
  return data
}
```

### Don't include single-item `getCustomer(id)` until something needs it

Knip flags it as dead code. Add it when you actually build a detail page;
list pages don't need it.

## Layer 2 — TanStack Query

Wrap each function in a hook OR call directly in the page (the codebase
currently does direct calls — `useQuery({ queryKey, queryFn: () => getCustomers(...) })`).
Both are fine. Pick one per entity and be consistent.

### Read

```tsx
import { useQuery } from '@tanstack/react-query'
import { useDebouncedSearch } from '@/hooks/useDebouncedSearch'

const [filter, setFilter] = useState('')
const [statusFilter, setStatusFilter] = useState<CustomerStatus | 'all'>('all')
const [skipCount, setSkipCount] = useState(0)

const { effective: effectiveFilter, status: searchStatus } = useDebouncedSearch(filter)

const { data, isLoading, isFetching } = useQuery({
  queryKey: ['customers', effectiveFilter, statusFilter, skipCount],
  queryFn: () =>
    getCustomers({
      filter:  effectiveFilter || undefined,
      status:  statusFilter === 'all' ? undefined : statusFilter,
      skipCount,
      maxResultCount: PAGE_SIZE,
      sorting: 'creationTime desc',
    }),
})
```

Rules of thumb:

- **Query key = every input that affects the request**, in stable order.
  React Query refetches automatically when any element changes.
- **Use `effectiveFilter` (debounced+gated) in the key**, not the raw
  `filter`. Otherwise you'd thrash the cache on every keystroke.
- **`'all'` sentinel** on nullable enum filters; map to `undefined` in
  the request so the backend doesn't filter.
- **Reset `skipCount` to 0** in the filter setter, not in the key —
  changing filters and landing on an empty page 5 is a UX bug.

### Write — mutations

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

const queryClient = useQueryClient()

const createMutation = useMutation({
  mutationFn: createCustomer,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['customers'] })
    setIsFormOpen(false)
    toast.success(t('AbpUi::SavedSuccessfully'))
  },
  onError: () => toast.error(t('AbpUi::Error')),
})

const updateMutation = useMutation({
  mutationFn: ({ id, input }: { id: string; input: CreateUpdateCustomerDto }) =>
    updateCustomer(id, input),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['customers'] })
    /* close dialog + reset state */
    toast.success(t('AbpUi::SavedSuccessfully'))
  },
  onError: () => toast.error(t('AbpUi::Error')),
})

const deleteMutation = useMutation({
  mutationFn: deleteCustomer,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['customers'] })
    toast.success(t('AbpUi::DeletedSuccessfully'))
  },
  onError: () => toast.error(t('AbpUi::Error')),
})
```

**Mandatory:** every successful mutation invalidates the list query key
(`['customers']` — without filter args, which invalidates ALL variants).

### Lifecycle mutations — surface the server error

When the backend throws `BusinessException` (e.g. invalid status
transition), the localized message is on `error.response.data.error.message`.
Show it verbatim — it's already in the user's culture.

```tsx
const statusMutation = useMutation({
  mutationFn: ({ id, status }: { id: string; status: CustomerStatus }) =>
    changeCustomerStatus(id, status),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['customers'] })
    toast.success(t('AbpUi::SavedSuccessfully'))
  },
  onError: (err: unknown) => {
    const e = err as { response?: { data?: { error?: { message?: string } } } }
    toast.error(e?.response?.data?.error?.message ?? t('AbpUi::Error'))
  },
})
```

## Layer 3 — multi-tenancy

The axios interceptor adds the `__tenant` header automatically when
`sessionStorage['abp_tenant_id']` is set (the TenantSwitch component
manages this). **You don't add tenant logic to your queries** — it's
transparent.

What you DO need to think about:

- **Permission strings**: `Ibl360.{Plural}.*` permissions are
  `MultiTenancySides.Tenant` by default (see `abp-feature-dev` Q2). That
  means the host admin user can't operate without first switching into a
  tenant context. If you smoke-test the page as host and see a 403, that's
  the multi-tenancy gate. Use the TenantSwitch chip in the header.
- **Cache invalidation on tenant switch**: TenantSwitch triggers a full
  `window.location.reload()` after `setTenantId(...)`. This clears React
  Query's cache implicitly, so you don't need cross-tenant cache logic.

## Layer 4 — permission-gated UI

Two layers of gating:

1. **Route guard** (`createPermissionGuard`) — blocks page rendering for
   unauthorized users.
2. **Per-button checks** (`usePermissions().isGranted(...)`) — hides
   actions the user can't perform.

```tsx
const { isGranted } = usePermissions()
const canCreate = isGranted('Ibl360.Customers.Create')
const canEdit   = isGranted('Ibl360.Customers.Edit')
const canDelete = isGranted('Ibl360.Customers.Delete')

{canCreate && <Button variant="accent">+ Nuovo cliente</Button>}

{canDelete && (
  <DropdownMenuItem
    className="text-error focus:text-error"
    onClick={onDelete}
  >
    {t('AbpUi::Delete')}
  </DropdownMenuItem>
)}
```

**Don't show a button just to make it disabled** — hide it. Disabled
buttons are confusing ("why can't I click this?"); permission-aware
UIs only show what the user can do.

## End-to-end checklist

When the backend contract is ready, you walk this list:

1. **Create `lib/api/{entityCamel}.ts`** — types + endpoint functions
   (template above).
2. **Build the page**:
   - State: filters + skipCount + dialog/confirm flags
   - `useDebouncedSearch` for the text filter
   - `useQuery` for the list
   - `useMutation` for create / update / delete (and lifecycle, if any)
   - Permission gates (`usePermissions()`)
   - Render: header + filter toolbar + table (lg+) / card-list (<lg) +
     pagination + ConfirmDialog + Create/Edit Dialog + mobile FAB
3. **Register the route** in `routes/router.tsx` with
   `createPermissionGuard('Ibl360.{Plural}')`.
4. **Add the sidebar entry** in `lib/routing/route-config.ts` (`group`,
   `nameKey`, `fallbackName`, `icon`, `requiredPolicy`).
5. **Add i18n keys** to all 4 `.json` files in `Ibl360/Localization/Ibl360/`
   (page title, field labels, enum values, permission labels, delete
   confirmation, lifecycle errors). See `i18n.md` for the full list.
6. **Verify**: `npx tsc --noEmit -p tsconfig.app.json`, then hard refresh
   the browser, log in as a tenant admin, run a create/edit/delete loop.

See `page-pattern.md` for the full Page-component template and
`shared-components.md` for the catalog of primitives.

## Common pitfalls

| Symptom | Cause |
|---|---|
| Filter resets on every keystroke | Used `filter` in queryKey instead of `effectiveFilter` (debounced one) |
| "Save" succeeds but the table still shows old data | Forgot `queryClient.invalidateQueries` in the mutation's `onSuccess` |
| 403 on every request as host admin | Permission is `MultiTenancySides.Tenant` — switch to a tenant or relax to `Both` (see abp-feature-dev) |
| Empty filter sends `?filter=` and returns nothing | Didn't strip empty string to `undefined` in the API client |
| Enum filter sends `?status=2` instead of `?status=Active` | DTO type still uses TS numeric enum — switch to string union (the wire format is strings) |
| `Menu:Foo` appears raw in the sidebar after adding a new key | Hard refresh — the i18n bundle is cached in memory |
| Date input rejects existing value on edit | `form.reset({ publishedAt: dto.publishedAt?.slice(0, 10) })` — `<input type="date">` wants `YYYY-MM-DD` only |
| Mutation fires but no toast / dialog never closes | `mutationFn` is `async` but you `await`ed it manually — let TanStack Query handle the lifecycle |
