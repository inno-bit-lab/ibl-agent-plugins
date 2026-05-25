# API client module

One file per entity at `react/src/lib/api/{entityCamel}.ts`. Mirrors the
backend AppService one-to-one: same DTO shapes, same endpoints, same enum
values.

> **See also:** `data-fetching.md` covers the end-to-end Backend→UI
> hand-off (TanStack Query wiring, mutations, permissions, debounced
> search). This file is the **transport layer** — types + endpoint
> functions. The hooks that consume these live in the page.

## Anatomy

```
1. Enum string unions (NOT TS `enum`)
2. Option arrays for selects (value + i18n key)
3. DTO interfaces (output, input, filter input, paged result)
4. Plain async functions wrapping axios
```

The shared `api` instance from `lib/api/axios.ts` already handles:
- Bearer token (from OIDC user manager)
- `__tenant` header (from sessionStorage)
- 401 → login redirect
- 403 → `/403` redirect (unless `skip403Redirect: true`)
- `Accept-Language` from current i18n culture

So each per-entity module is **just types + endpoint paths**.

## Template

```ts
/**
 * {Entity}s API - I{Entity}AppService.
 * Tenant-scoped: requires __tenant header (handled by axios interceptor when
 * sessionStorage 'abp_tenant_id' is set).
 *
 * Enums are serialized as strings on the backend (BsonRepresentation.String +
 * JsonStringEnumConverter). Keep these TS unions in sync with the C# enums.
 */
import { api } from './axios'

// 1. Enum string unions — match C# enum NAMES exactly
export type {Entity}Status = 'Prospect' | 'Active' | 'Churned'
export type {Entity}Segment = 'Smb' | 'Enterprise' | 'Public'

// 2. Option arrays for <Select> components.
//    The `key` is the name-based localization key — matches the backend
//    Localization/*.json keys (Enum:{EnumName}.{ValueName}).
export const {entityCamel}StatusOptions: { value: {Entity}Status; key: string }[] = [
  { value: 'Prospect', key: 'Enum:{Entity}Status.Prospect' },
  { value: 'Active',   key: 'Enum:{Entity}Status.Active' },
  { value: 'Churned',  key: 'Enum:{Entity}Status.Churned' },
]

// 3. DTOs — match the C# DTO field names case-insensitively (System.Text.Json
//    defaults to camelCase on the wire).
export interface {Entity}Dto {
  id: string
  legalName: string
  // ... one field per property in {Entity}Dto.cs
  segment: {Entity}Segment
  status: {Entity}Status
  statusChangedAt?: string | null
  creationTime?: string
  lastModificationTime?: string | null
}

export interface CreateUpdate{Entity}Dto {
  legalName: string
  // ... matches CreateUpdate{Entity}Dto.cs
  segment: {Entity}Segment
}

export interface Get{Entities}Input {
  filter?: string
  status?: {Entity}Status
  segment?: {Entity}Segment
  createdFrom?: string  // ISO date
  createdTo?: string
  maxResultCount?: number
  skipCount?: number
  sorting?: string      // e.g. "creationTime desc"
}

export interface PagedResultDto<T> {
  items: T[]
  totalCount: number
}

// 4. Endpoint functions. URL is /app/{entity-kebab}/... — the route ABP
//    generates from the AppService. Plural names get pluralized by ABP only
//    for top-level paths — verify with Swagger if unsure.
export async function get{Entities}(
  params: Get{Entities}Input = {}
): Promise<PagedResultDto<{Entity}Dto>> {
  const { data } = await api.get<PagedResultDto<{Entity}Dto>>('/app/{entityKebab}', {
    params: {
      filter:        params.filter || undefined,    // strip empty strings
      status:        params.status,
      segment:       params.segment,
      createdFrom:   params.createdFrom || undefined,
      createdTo:     params.createdTo || undefined,
      maxResultCount: params.maxResultCount ?? 10,
      skipCount:      params.skipCount ?? 0,
      sorting:        params.sorting,
    },
  })
  return data
}

export async function get{Entity}(id: string): Promise<{Entity}Dto> {
  const { data } = await api.get<{Entity}Dto>(`/app/{entityKebab}/${id}`)
  return data
}

export async function create{Entity}(
  input: CreateUpdate{Entity}Dto
): Promise<{Entity}Dto> {
  const { data } = await api.post<{Entity}Dto>('/app/{entityKebab}', input)
  return data
}

export async function update{Entity}(
  id: string,
  input: CreateUpdate{Entity}Dto
): Promise<{Entity}Dto> {
  const { data } = await api.put<{Entity}Dto>(`/app/{entityKebab}/${id}`, input)
  return data
}

export async function delete{Entity}(id: string): Promise<void> {
  await api.delete(`/app/{entityKebab}/${id}`)
}

// Optional — only if the entity has a lifecycle method on the AppService
export async function change{Entity}Status(
  id: string,
  status: {Entity}Status
): Promise<{Entity}Dto> {
  const { data } = await api.post<{Entity}Dto>(
    `/app/{entityKebab}/${id}/change-status`,
    { status }
  )
  return data
}
```

## Why string unions, not TS `enum`

TS `enum` emits runtime code, which clashes with `erasableSyntaxOnly` in
modern tsconfigs (Vite/SWC). String unions are erased at compile time and
align perfectly with the wire format (`"Active"`, not `1`).

Existing `BookType` enum in this project predates the convention — if you
edit `books.ts` for an unrelated reason, leave the enum alone (changing it
is a typing migration, not a drive-by).

## Strip empty strings from query params

`axios` serializes `{ foo: '' }` as `?foo=` which the backend treats as a
filter for empty string. Always coerce empty input to `undefined`:

```ts
params: { filter: params.filter || undefined }
```

The Page should do the same when reading from a controlled input.

## Do not add single-item fetchers until the UI needs them

`getCustomer(id)` and similar `getById` functions are dead weight when
the list page is the only consumer (CRUD pages already have the entity
object in `items`). Add them only when a detail page is built — `knip`
flags unused exports otherwise and the diff stays small.

## When the backend changes

Two options:

- **Hand-edit** the API module — fine for one or two field changes.
- **Regenerate** via `yarn generate-proxy` (the `abp generate-proxy -t js`
  command in `package.json`). Regen produces JavaScript proxies, not the
  hand-curated TS shape used here — only useful as a starting point, the
  resulting files usually need to be reformatted to match this template.

For modifications of an existing client, see `modify-delete.md`.
