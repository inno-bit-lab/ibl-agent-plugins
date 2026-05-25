# Modify and Delete workflows (backend)

This file is the backend counterpart of `abp-react-ui/references/modify-delete.md`.
The two pair up: most changes touch both sides, and a change is only
"done" when both have been migrated.

## MODIFY — common changes and their impact maps

### Add a property to an entity

| File | Change |
|---|---|
| `Entities/{Plural}/{Entity}.cs` | Add property |
| `Services/Dtos/{Plural}/{Entity}Dto.cs` | Add property (output) |
| `Services/Dtos/{Plural}/CreateUpdate{Entity}Dto.cs` | Add property with DataAnnotation (Required, StringLength, …) |
| `Services/{Plural}/{Entity}AppService.cs` `CreateAsync` / `UpdateAsync` | Map new property (or rely on Mapperly if names match) |
| `ObjectMapping/*Mappers.cs` | If using `RequiredMappingStrategy.Target` and names match, auto. If diverge, add `[MapProperty]`. |
| `Localization/{ResourceName}/*.json` | Add label key in every language |
| Index (if filtered or queried) | Add via `Data/{Entity}IndexInitializer.cs` |
| Existing data | New property is `null` / default on existing documents. Backfill via `updateMany` if business rule requires non-null. |
| Frontend | Delegate to `abp-react-ui` Modify workflow |

### Add a filter (typed)

| File | Change |
|---|---|
| `Services/Dtos/{Plural}/Get{Entities}Input.cs` | Add nullable property |
| `Services/{Plural}/{Entity}AppService.cs` `ApplyFilters` | Add `if (input.{Field}.HasValue) q = q.Where(…)` clause |
| Index | Add index on the new filter column if it's high-cardinality and frequently queried |
| Locale `.json` | Add label only if the filter has a UI representation needing translation (rare for the backend) |
| Frontend | Delegate to `abp-react-ui` |

### Rename a property

The highest-impact change. Always grep the whole solution:

```
Grep "OldName" --type cs
Grep "OldName" --type tsx
Grep "OldName" --type json
```

Expected hits: entity, all DTOs, AppService LINQ, mapper attributes,
locale label keys, index initializer, frontend api module, frontend page,
frontend locale, integration tests.

Rename in this order to minimize broken build states:

1. Entity property (forces every consumer to fail compilation)
2. All DTOs that mirror the entity
3. AppService LINQ
4. Mapper attributes
5. Tests
6. `dotnet build` — should pass
7. Locale `.json` (rename keys, keep old as fallback if existing UIs depend on them)
8. Index initializer
9. Frontend (delegate to `abp-react-ui`)
10. Data migration: `db.{Plural}.updateMany({}, { $rename: { OldName: NewName } })` — **surface to the user**, never run silently

### Change permission policy name

| File | Change |
|---|---|
| `Permissions/*Permissions.cs` constant value | Rename |
| `Permissions/*PermissionDefinitionProvider.cs` `AddPermission` | Update string |
| `[Authorize(...)]` on AppService methods | Update string |
| Integration tests granted-policy lists | Update string |
| Frontend `route-config.ts` `requiredPolicy` | Update string |
| Frontend page `isGranted(...)` calls | Update string |
| Frontend router `createPermissionGuard(...)` | Update string |
| Role permission grants in DB | Migrate: grant the new policy to roles that had the old one, otherwise users lose access |

### Change `MultiTenancySides` of a permission

`Tenant` → `Both` (or vice-versa) doesn't need a data migration — only
re-seed:

```bash
powershell -File migrate-database.ps1
```

If you tightened from `Both` → `Tenant`, host users with the existing
grant lose access immediately. Warn before.

### Add a lifecycle transition

| File | Change |
|---|---|
| `Entities/{Plural}/{Entity}.cs` `AllowedTransitions` dictionary | Add the entry |
| `Entities/{Plural}/{EnumName}.cs` | Add the new value if introducing a state |
| `Localization/*.json` | Add `Enum:{EnumName}.{NewValue}` keys |
| Frontend | Delegate to `abp-react-ui` (add menu item conditionally for the new transition) |

### Switch entity from `Audited` to `FullAudited` (or vice-versa)

Adding soft-delete after the fact:

| File | Change |
|---|---|
| `Entities/{Plural}/{Entity}.cs` base class | `AuditedAggregateRoot<Guid>` → `FullAuditedAggregateRoot<Guid>` |
| `Services/Dtos/{Plural}/{Entity}Dto.cs` base class | `AuditedEntityDto<Guid>` → `FullAuditedEntityDto<Guid>` |
| Existing data | `IsDeleted = false` default — all existing rows remain visible. Safe. |

Removing soft-delete (rare, mostly a mistake): existing rows with
`IsDeleted=true` become visible again. Decide before downgrading whether
to hard-delete those rows first.

### Add `IMultiTenant` to an existing entity

Delegate to `abp-multitenancy`. Existing rows get `TenantId = null`,
which means "host" — so under tenant data filter they become invisible
to tenants. **Surface this** — usually the user wants to backfill the
right tenant id before activating the filter.

## DELETE — removing a feature cleanly

Detailed order in the main SKILL.md. The high points:

1. **Locale `.json` keys** first (no compile dependency).
2. **Permission constants & provider** — forces `[Authorize]` to fail.
3. **AppService + interface** — forces consumers to fail.
4. **DTOs**.
5. **Mapper**.
6. **Custom repository** + **IndexInitializer**.
7. **DbContext registration** (remove collection + entity registration).
8. **Entity + enums**.
9. **`*DomainErrorCodes.cs`** — remove lifecycle errors.
10. **Tests**.
11. `dotnet build` — should pass.
12. **MongoDB collection** — manual `drop()`, never automatic.
13. **Role permission grants** — orphan cleanup.
14. **`migrate-database`** to refresh the seed.
15. **Frontend** — delegate to `abp-react-ui`.

The reason for this order: each step makes the build fail in a way that
points to the next thing to remove. Walking it in the wrong direction
means working through stale errors on already-broken code.

## Important: don't run data migrations automatically

For any change that affects MongoDB storage (renaming a field, removing
a collection, changing enum representation, removing soft-delete), the
data in the cluster is the user's responsibility, not Claude's.

The right pattern is:

1. Describe the change you made to the schema/code.
2. Describe what would happen to existing data (orphan field, dual-read,
   loss of visibility).
3. Quote the Mongo shell command they'd run.
4. **Wait for them to decide**.

This applies equally for renames, lifecycle changes, multi-tenancy
toggles, and outright deletes. The cost of an "oh I'll handle the data
later" is usually low; the cost of a silent migration that wipes a
production collection is catastrophic.
