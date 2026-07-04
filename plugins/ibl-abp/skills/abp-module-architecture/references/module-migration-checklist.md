# Module Migration Checklist

Use this when moving existing host resources into ABP modules.

The analyzer auto-detects the template, so the steps below apply to both. The
difference is where each concern lives. In **nolayers** a bounded context's
resources sit in one project under concern-named folders (`Entities/`,
`Services/`, `Permissions/`, `Data/`), namespaced `Root.Entities.{Plural}`,
`Root.Services.{Plural}`, etc. In **layered** the same context fans out across
separate layer projects with a flat `Root.{Plural}` namespace, so every layer's
slice of the aggregate moves together:

| Layer project | Aggregate slice it holds |
|---|---|
| `*.Domain/{Plural}/` | entity, repository interface, domain service, data seed |
| `*.Domain.Shared/` | enums, constants, error codes, ETOs, localization |
| `*.Application.Contracts/` | DTOs, AppService interface, permissions |
| `*.Application/` | AppService implementation, object mapper |
| `*.MongoDB/` | Mongo context, repository implementation |

Move the matching tests (`*.Domain.Tests`, `*.Application.Tests`,
`*.MongoDB.Tests`) and React UI alongside them. `abp-core`'s `resolve_artifact()`
is the source of truth for these paths and namespaces.

## 1. Inventory

Run:

```powershell
python <skills-root>/abp-module-architecture/scripts/analyze_module_ownership.py --solution .
```

Capture:

- `Entities/**`
- `Services/**`
- `Services/Dtos/**`
- `Permissions/**`
- `*DomainErrorCodes.cs`
- Mongo context and index seed contributors
- `Localization/**`
- tests
- React pages, API clients, components, hooks, route/menu entries

In a layered solution these globs resolve against the layer projects listed
above rather than one host project; the analyzer reports them grouped per
concern regardless.

## 2. Backend Move

- Move contracts first: DTOs, service interfaces, permission constants,
  localization resource, domain error codes.
- Move domain/application implementation into the module assembly.
- Rewrite namespaces to module ownership.
- Register conventional controllers in the module:

```csharp
Configure<AbpAspNetCoreMvcOptions>(options =>
{
    options.ConventionalControllers.Create(typeof(MyModule).Assembly);
});
```

- Add the module as an application part if the host needs controller discovery:

```csharp
PreConfigure<IMvcBuilder>(mvcBuilder =>
{
    mvcBuilder.AddApplicationPartIfNotExists(typeof(MyModule).Assembly);
});
```

- Move Mongo collections and indexes into the module context.
- Keep collection names stable unless a data migration intentionally renames
  them.
- Move object mapping into the module and set `ObjectMapperContext`.
- Remove module-owned permissions/error codes from the host.

## 3. Permission Migration

Changing `Ibl360.Customers` to `Ibl360Crm.Customers` creates new permission
definitions but does not automatically grant them to existing roles.

Required:

- Seed the new module permissions for default tenant roles.
- In the standalone `*.DbMigrator` console project, add
  `[DependsOn(typeof(<CustomModule>Module))]` for every custom module whose
  `IDataSeedContributor` or `PermissionDefinitionProvider` must run. If the
  migrator does not depend on the module, its Contracts are not loaded and its
  seeds/permission grants never execute.
- Run the migrator/seeder after the move.
- Verify that the module's seed contributor actually ran and that the new
  permissions exist in the permission store. Do not treat "migrator completed"
  as proof that the module's grants were created.
- Refresh/re-login in React so `application-configuration` returns the new
  granted policies.

Symptom: routes exist, menu items exist, but the menu group disappears because
all children are filtered by missing `requiredPolicy`.

## 4. Localization

- Copy module-owned keys into the module resource.
- Change exception keys to the new module code namespace.
- Map exception namespace:

```csharp
options.MapCodeNamespace("Ibl360Crm", typeof(Ibl360CrmResource));
```

- Remove moved keys from the host resource to avoid stale ownership.

## 5. React Move

Recommended layout:

```text
modules/<module>/react/src/
  module.ts
  pages/
  components/
  lib/api/

modules/<shared>/react/src/
  module.ts
  components/ui/
  components/<shared-domain>/
  hooks/
  lib/
```

Host responsibilities:

- `react/src/modules/registry.ts`
- app shell, auth, tenant switch, theme, root router
- shared aliases in Vite and TypeScript

Module responsibilities:

- module-local routes and menu entries
- module-local API clients and pages
- module permissions in `beforeLoad` and `requiredPolicy`

Tailwind v4 must scan module folders:

```css
@source "../../../modules/ibl360shared/react/src";
@source "../../../modules/ibl360crm/react/src";
```

If the UI loses styling after the move, this is the first thing to check.

## 6. Verification

Run the evidence commands before claiming the migration is complete:

```powershell
dotnet build .\MySolution.slnx --no-restore
dotnet test .\MySolution.slnx --no-build
npm run build
```

Then run a reference grep:

```powershell
rg "OldHost\.(Customers|Suppliers)|OldHost:(Customers|Suppliers):|@/components/ui" `
  --glob "!**/bin/**" --glob "!**/obj/**" --glob "!**/node_modules/**" `
  --glob "!**/dist/**"
```

Finally, start backend/frontend and verify:

- backend health endpoint returns 200
- frontend returns 200
- browser console has no CORS errors
- menu items appear for a user with the new module permissions
