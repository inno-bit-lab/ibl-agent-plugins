# Modify and Delete workflows (no scripts)

These workflows are intentionally **manual** (Claude grep + edit) because
the right answer depends on what else references the entity. A script
would either over-edit (breaking unrelated code) or under-edit (leaving
dangling references). Claude's job is to identify the impact map, make
the change, and verify nothing broke.

## MODIFY — common changes and their impact maps

### Add a filter (e.g. add `Country` filter to Customers list)

| File | Change |
|---|---|
| `lib/api/{entity}.ts` | Add `country?: string` to `Get{Entities}Input`; pass it through in `get{Entities}()` |
| `pages/{plural}/{Entity}Page.tsx` | New `useState` for the filter; new widget in the filter bar; add to the query key; map `'all'`/`''` → `undefined` |
| Backend `Get{Entities}Input.cs` | Add the property |
| Backend `{Entity}AppService.cs` `ApplyFilters` | Add the LINQ clause |
| Locale `.json` | Add labels if the filter has a `<SelectItem>` "All" option keyed by `::All` |

The localization key for the column header probably already exists from
the table. Don't duplicate.

### Add a column

| File | Change |
|---|---|
| `lib/api/{entity}.ts` | Add the property to `{Entity}Dto` |
| `pages/{plural}/{Entity}Page.tsx` | New `<TableHead>` + `<TableCell>` |
| Backend `{Entity}Dto.cs` | Add the property |
| Backend mapper | If the mapper uses `RequiredMappingStrategy.Target`, the new property auto-maps if the entity has it. If not, add an explicit mapping. |
| Locale `.json` | Add label key for the new header |

If the column is an enum: also add the enum value localization keys
(`Enum:{EnumName}.{Value}`) — same pattern as the existing enums.

### Add a form field

| File | Change |
|---|---|
| `lib/api/{entity}.ts` | Add to `CreateUpdate{Entity}Dto` |
| `pages/{plural}/{Entity}Page.tsx` | Zod schema entry; `defaultValues`; `openEdit` reset; `<Field>` block; `onSubmit` mapping (if normalization needed) |
| Backend `CreateUpdate{Entity}Dto.cs` | Add property + DataAnnotation |
| Backend `{Entity}AppService` | `Create`/`Update` consume new property |
| Backend mapper | Same as column |
| Locale `.json` | Add field label key |

### Rename a property (e.g. `LegalName` → `RegisteredName`)

| File | Change |
|---|---|
| Backend `{Entity}.cs` | Rename property |
| Backend `{Entity}Dto.cs`, `CreateUpdate{Entity}Dto.cs` | Rename property |
| Backend `{Entity}AppService` `ApplyFilters` | Update LINQ |
| Backend mapper | If mapper uses convention-based mapping (same name source/target), works automatically. If property name diverges, add explicit `[MapProperty]`. |
| Backend `Localization/*.json` | Rename label key, OR keep old key with new value (avoid touching keys callers depend on) |
| Backend index initializer (if indexed) | Update `Builders<>.IndexKeys.Ascending(...)` |
| Frontend `lib/api/{entity}.ts` | Rename in `Dto`, `CreateUpdate`, `Get{Entities}Input` (if filtered) |
| Frontend `pages/{plural}/{Entity}Page.tsx` | Update column header `t('NewKey')`, `<TableCell>`, Zod schema key, form `<Field>`, `openEdit` mapping, `onSubmit` mapping, `defaultValues` |
| Frontend locale `.json` | Add new key + (optionally) keep the old as alias |
| Migration of existing data | MongoDB: write an `updateMany` to rename the field; SQL: rename column. **Surface this to the user** — never run silently. |

Renames are the highest-impact change. Always grep the whole repo for the
old name (`Grep "LegalName" --type cs` and `--type tsx`) and walk through
each match.

### Rename an enum value (e.g. `Smb` → `Small`)

This is functionally a data migration. The wire format and the storage
both change, plus all localization keys.

| File | Change |
|---|---|
| Backend `{EnumName}.cs` | Rename member |
| Backend `Localization/*.json` | Rename `Enum:{EnumName}.Smb` key to `Enum:{EnumName}.Small` (in every language file) |
| Frontend `lib/api/{entity}.ts` | Update string union, options array (both `value` and `key`) |
| Frontend page | Update any hardcoded checks (e.g. lifecycle conditions: `c.status === 'Smb'` → `'Small'`) |
| Existing MongoDB data | Run `updateMany` mapping `Smb` → `Small`. Required: the convention reads what's there, doesn't translate it. |

Reordering enum members (e.g. moving `Active` from second to first) is
**safe** under the string-storage convention, **catastrophic** under
int storage. If you're modifying enum order, run the
`abp-mongodb/scripts/verify_enum_string_setup.py` first to confirm string
storage is in place.

### Add a lifecycle transition (e.g. `Active → Suspended`)

| File | Change |
|---|---|
| Backend `{Entity}.cs` `AllowedTransitions` dictionary | Add the new transition |
| Backend `{EnumName}.cs` | Add the new state (if new) |
| Backend `Localization/*.json` | Add `Enum:{EnumName}.{NewValue}` keys |
| Frontend `lib/api/{entity}.ts` | Update enum string union + options array |
| Frontend page | Add the new conditional `<DropdownMenuItem>` in the action menu |

The backend `BusinessException` thrown on illegal transitions doesn't
need changes — it's already generic.

### Change a permission policy

The permission name is referenced in many places. Carefully:

| File | Change |
|---|---|
| Backend `*Permissions.cs` | Rename constant value |
| Backend `*PermissionDefinitionProvider.cs` | Update reference |
| Backend `[Authorize(...)]` attributes on AppService | Update string reference |
| Backend tests (if any) | Update granted-policy lists |
| Frontend `route-config.ts` `requiredPolicy` | Update string |
| Frontend page `usePermissions().isGranted(...)` calls | Update string |
| Frontend router `createPermissionGuard(...)` | Update string |
| Existing role assignments in DB | Run a migration script to grant the new policy name to roles that had the old one — otherwise users lose access. |

Always surface the "data migration" item to the user explicitly.

## DELETE — removing a feature cleanly

Removing a feature in the wrong order leaves broken intermediate states
(404 from sidebar, dangling imports, etc.). Follow this order.

### Frontend side

1. **`route-config.ts`** — remove the menu entry. Now invisible.
2. **`router.tsx`** — remove the import and the `addChildren` reference.
3. **`pages/{plural}/`** — delete the folder.
4. **`lib/api/{entityCamel}.ts`** — delete the file. Before deletion,
   grep the project for imports of this file; surface any other pages
   that still depend on it.
5. **Locale `*.json`** — remove keys: `Menu:{Plural}`, `{Plural}`,
   `{Entity}`, `New{Entity}`, all `{Field}` labels not shared with
   other entities, `Permission:{Plural}*`,
   `{Entity}DeletionConfirmationMessage`, all `Enum:{EnumName}.*` for
   any enum only this entity used, lifecycle error codes
   (`{Ns}:{Plural}:*`).
6. Optionally: `tsx test files`.

After each chunk, run `npx tsc --noEmit -p tsconfig.app.json` to catch
broken references.

### Backend side (delegate to `abp-feature-dev` MODIFY/DELETE workflow)

The frontend delete doesn't remove the AppService — the API endpoints
still exist. If the user wants the backend removed too:

| File | Action |
|---|---|
| `Entities/{Plural}/` | Delete folder |
| `Services/Dtos/{Plural}/` | Delete folder |
| `Services/{Plural}/` | Delete folder |
| `Data/{Plural}/` (custom repo if any) | Delete folder |
| `Data/{Entity}IndexInitializer.cs` (if exists) | Delete file |
| `Data/*MongoDbContext.cs` | Remove `IMongoCollection<{Entity}>` line + `modelBuilder.Entity<{Entity}>(...)` block |
| `Permissions/*Permissions.cs` | Remove the `{Plural}` static class |
| `Permissions/*PermissionDefinitionProvider.cs` | Remove the `AddPermission` block |
| `ObjectMapping/*Mappers.cs` | Remove the Mapperly mapper for this entity |
| `Localization/{ResourceName}/*.json` | Remove keys (see frontend list) |
| `*DomainErrorCodes.cs` (if lifecycle) | Remove the nested class |
| MongoDB collection itself | **Don't drop automatically.** Surface to the user: "The Mongo collection `Customers` still contains data. Run `db.Customers.drop()` manually if you want a clean slate." |
| Role permission grants (DB) | Existing role grants for the deleted permission constants become orphan. Harmless but ugly — flag for cleanup. |

The backend delete needs a `dotnet build` to validate, and then a
`migrate-database` to refresh the seed (so the deleted permissions are
removed from the admin UI's permission tree).

## Tips for both Modify and Delete

- **Grep the whole repo before changing anything**. `Grep "Customer"
  --type cs` and `--type tsx`. Sometimes a property is read in
  unexpected places (a search bar in a dashboard, an export script,
  another page's filter).
- **Show the user the impact list before editing**. They might know
  the change is bigger than you think ("oh wait, we also have a custom
  Customer report under `/reports/customer-pipeline`").
- **Edit in chunks**, not all at once. After each chunk, `tsc` + `dotnet
  build` (depending on side). Catching one mismatch is much easier than
  unwinding ten.
- **Don't touch git history**. Make new commits, don't amend, never
  force push.
- **Surface data migrations explicitly**. Renaming a Mongo field
  doesn't rewrite existing documents — the user must decide whether to
  run the `updateMany`, leave dual-read, or accept data loss.
