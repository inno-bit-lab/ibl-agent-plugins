# Routing + sidebar menu

Two files to touch for every page:
- `src/routes/router.tsx` — the route + permission guard
- `src/lib/routing/route-config.ts` — the sidebar entry (optional)

> **Sibling references:** `shared-components.md` documents `<Sidebar>` /
> `<RailTooltip>` (which `route-config` drives). `design-tokens.md` for
> visual styling. The `group` field on each route item controls which
> sidebar section it lands in (`overview` | `admin`).

## Router

```tsx
// 1. Import at the top
import { {Entity}Page } from '@/pages/{plural}/{Entity}Page'

// 2. Declare the route. Always pair the page with a permission guard
//    via createPermissionGuard — the page itself ALSO checks
//    granular permissions for buttons, but the route guard
//    short-circuits unauthorized users before the page even mounts.
const {entityCamel}Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/{plural-kebab}',
  component: {Entity}Page,
  beforeLoad: createPermissionGuard('{RootNs}.{Plural}'),
})

// 3. Append to the rootRoute.addChildren([...]) call. The order in this
//    array doesn't affect the URL hierarchy (each route declares its own
//    parent), but keep the file readable by grouping related routes.
const routeTree = rootRoute.addChildren([
  indexRoute,
  forbiddenRoute,
  accountRoute,
  identityRoute,
  booksRoute,
  {entityCamel}Route,   // <- here
])
```

The permission policy passed to `createPermissionGuard` is the **parent**
permission (e.g. `Ibl360.Customers`), not a child like
`Ibl360.Customers.Create`. Granting the parent implies read access;
the page handles finer gating itself.

## Sidebar menu entry

```ts
// route-config.ts — append to the array, choose a sensible `order`
{
  path: '/{plural-kebab}',
  nameKey: 'Menu:{Plural}',
  fallbackName: '{Plural}',         // MANDATORY — see below
  icon: {LucideIcon},
  order: {N},
  group: 'overview',                // 'overview' | 'admin' — sidebar section
  requiredPolicy: '{RootNs}.{Plural}',
},
```

The `group` field places the entry under either the "PANORAMICA" or
"AMMINISTRAZIONE" sidebar section (rendered by `<Sidebar>`). First-class
CRUD entities → `overview`. Admin / config tools → `admin`. Omit for the
implicit "overview".

Pick the icon from `lucide-react` so it matches the existing toolbar. Common
choices:

| Domain | Icon |
|---|---|
| Customers / clients | `Building2`, `Users2` |
| Orders / transactions | `ShoppingCart`, `Receipt` |
| Products / catalog | `Package`, `Boxes` |
| Documents / files | `FileText`, `Files` |
| Settings | `Settings`, `Cog` |
| Reports / analytics | `BarChart3`, `LineChart` |

Don't reuse `BookOpen` (Books), `Users` (Identity), `ShieldCheck` (Admin
Console), `Home` — they're already taken.

### `fallbackName` is mandatory

The sidebar renders before the i18n bundle finishes loading. Without
`fallbackName` the user briefly sees `Menu:Foo` (the raw key) until the
bundle resolves. With `fallbackName`, they see a human label immediately.

The Sidebar component uses:

```tsx
{t(item.nameKey, item.fallbackName ?? item.nameKey)}
```

The fallback also kicks in when:
- The backend is down at app boot (bundle fetch fails silently)
- The user just added a new key but didn't re-fetch (cache)
- The locale doesn't have the key yet

### Rail tooltips when collapsed

When the sidebar collapses (the FlowGest-style 72px rail), each nav item
shows its label as a portal-based tooltip on hover/focus. The Sidebar
wraps every item in `<RailTooltip label={collapsed ? label : undefined}>`
automatically — you don't need to do anything per-entry. See
`shared-components.md` → `<RailTooltip>` if you need to use it elsewhere.

### Permission policy hides the entry

`requiredPolicy: 'Ibl360.Customers'` makes the sidebar hide the entry for
users without that permission. The Sidebar respects this; you don't have
to wrap your entry in conditional logic.

### Grouped entries (children)

For nested menu items (e.g. a "Identity" group with Users + Roles children):

```ts
{
  path: '/identity',
  nameKey: 'AbpIdentity::Identity',
  fallbackName: 'Identity',
  icon: ShieldCheck,
  order: 5,
  requiresAuth: true,
  children: [
    {
      path: '/identity/users',
      nameKey: 'AbpIdentity::Users',
      fallbackName: 'Users',
      requiredPolicy: 'AbpIdentity.Users',
    },
    // ... more children
  ],
},
```

A parent with `children: [...]` becomes a collapsible group. If all
children are hidden by permissions, the parent auto-hides too.

If you're adding to an existing group, append to its `children` array.
If you're creating a new group, set its own `requiresAuth: true` (no
specific policy) and let the children carry the policies.

### External / non-SPA destinations

For links that should leave the SPA (e.g. legacy admin console):

```ts
{
  path: '/admin-console',
  nameKey: 'Menu:AdminConsole',
  fallbackName: 'Admin',
  icon: ShieldCheck,
  order: 6,
  requiresAuth: true,
  externalHref: getAdminConsoleUrl,     // resolver function
  externalTarget: '_blank',
  externalRel: 'noopener noreferrer',
},
```

The resolver runs at click time so it can read runtime config.

## When to skip the sidebar entry

Register the route in `router.tsx` but skip `route-config.ts` when:

- The page is only reachable from inside another page (e.g. a "View details"
  pane on a customer row).
- The page is a debug/admin tool not meant for everyday navigation.
- The page is parametric (e.g. `/customers/$id/timeline`) — render it but
  don't put it in the sidebar.

Parametric routes use TanStack Router's `$param`:

```tsx
const {entityCamel}DetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/{plural-kebab}/$id',
  component: {Entity}DetailPage,
  beforeLoad: createPermissionGuard('{RootNs}.{Plural}'),
})
```

## Verification

After adding the route + sidebar entry:

1. `npx tsc --noEmit -p tsconfig.app.json` — confirm imports resolve.
2. With Vite running, the sidebar entry appears if the logged-in user has
   the permission (need to run a re-seed or grant via Identity UI).
3. Clicking the entry routes to the page. Navigating directly (typing the
   URL) also works.
4. As a user without the permission, the entry is hidden, and direct URL
   access redirects to `/403`.

If the entry is visible but the page shows `Forbidden`, the route guard is
checking a different policy than the sidebar — they must match.

## Two-route pattern for complex entities

When the entity took the dedicated edit-page path (see
`complex-edit-page.md`), it has TWO routes, not one. Both point to
the same component:

```ts
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

Notes:
- `tanstack-router` uses `$id` (dollar) in the path for params, NOT `:id`.
- The two routes have DIFFERENT permission guards (`.Create` vs `.Edit`)
  — a user might be able to view + edit existing rows but not create
  new ones, or vice-versa. The list page Buttons must mirror this:
  hide "New" if no Create permission, hide "Edit" if no Edit permission.
- `useParams({ strict: false })` in the page component reads `id` and
  branches into create-mode (undefined) vs edit-mode (defined).
- Sidebar only shows the LIST route. `/new` and `/:id/edit` are
  reachable through buttons / row clicks; they don't get their own
  sidebar entry.
