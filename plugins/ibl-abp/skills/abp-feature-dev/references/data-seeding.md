# Data seeding patterns

This reference covers the **tenant data seed contributor** — the place
where new permissions need to be granted to default roles so that users
can see the new feature on first boot.

Most ABP projects have at least one custom `IDataSeedContributor` that:
1. Creates a "demo" / "default" tenant if it doesn't exist.
2. Seeds an admin user inside that tenant.
3. Grants application permissions to the admin role.

When you add a new entity with permissions, **step 3 needs to know about
them**. If you forget, the React permission guard (`requiredPolicy`) hides
the sidebar entry and the user calls you saying "the menu doesn't appear".

## Finding the contributor

It usually lives under `{Host}/Data/` with a name like:
- `*TenantDataSeedContributor.cs`
- `Demo*Seed*.cs`
- `DefaultDataSeedContributor.cs`

Look for one of these signals:
- Implements `IDataSeedContributor` AND injects `IPermissionManager`.
- Calls `SetForRoleAsync(...)` or a helper like `GrantIfMissingAsync(...)`.
- References specific permission constants (e.g. `{Module}Permissions.X`).

If nothing matches, the project may rely on the ABP default seeder (which
grants nothing custom) or on manual configuration via the Admin Console.
Surface this to the user — don't silently leave the new permissions
ungranted.

## Adding new permissions to an existing contributor

The pattern is simple — append the new permission constants to the same
block that grants existing ones:

```csharp
var adminRole = await _roleRepository.FindByNormalizedNameAsync("ADMIN");
if (adminRole != null)
{
    // Existing
    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.Customers.Default);
    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.Customers.Create);
    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.Customers.Edit);
    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.Customers.Delete);

    // NEW — replace {Entity} with the new entity name
    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.{Entity}.Default);
    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.{Entity}.Create);
    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.{Entity}.Edit);
    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.{Entity}.Delete);
}
```

The `GrantIfMissingAsync` helper is typically defined in the same file:

```csharp
private async Task GrantIfMissingAsync(string roleName, string permissionName)
{
    var grant = await _permissionManager.GetForRoleAsync(roleName, permissionName);
    if (!grant.IsGranted)
    {
        await _permissionManager.SetForRoleAsync(roleName, permissionName, true);
    }
}
```

After editing the contributor, run the migration to apply the grants:

```bash
# Windows / cross-platform
dotnet run --project {Host} -- --migrate-database

# Or the convenience script that most projects ship
./migrate-database.ps1
```

Then **restart the running backend** so the new `PermissionDefinitionProvider`
exposes the new permission names to the
`/api/abp/application-configuration` endpoint, and **hard-refresh the
React app** (Ctrl+F5) to bust the i18n cache for any new translation keys.

## The "FindByNameAsync returns null but Create says duplicate" trap

A specific bug pattern in ABP MongoDB seed contributors:

```csharp
// BUG: ITenantRepository.FindByNameAsync on Mongo does an exact-case
// Name match. CreateAsync's AbpTenantValidator deduplicates on
// NormalizedName. If the tenant already exists with a different casing
// (e.g. saved as "demo" but Name field stores "Demo"), the first lookup
// returns null and the Create throws BusinessException("...DuplicateName").
var tenant = await _tenantRepository.FindByNameAsync(TenantName);
if (tenant == null)
{
    tenant = await _tenantManager.CreateAsync(TenantName); // 💥 explodes
    await _tenantRepository.InsertAsync(tenant, autoSave: true);
}
```

The robust pattern: layer a NormalizedName lookup on top.

```csharp
var tenant = await _tenantRepository.FindByNameAsync(TenantName);
if (tenant == null)
{
    // Fall back to a case-insensitive search before deciding to create.
    var normalized = TenantName.ToUpperInvariant();
    var existing = await _tenantRepository.GetListAsync();
    tenant = existing.FirstOrDefault(t => t.NormalizedName == normalized);
}

if (tenant == null)
{
    tenant = await _tenantManager.CreateAsync(TenantName);
    await _tenantRepository.InsertAsync(tenant, autoSave: true);
    _logger.LogInformation("Created tenant {TenantId}", tenant.Id);
}
```

When auditing an existing contributor, scan for this pattern and offer
to fix it — even if not strictly needed today, it'll bite the next time
the seed runs against a non-empty database.

## Full template — new seed contributor from scratch

When the project has no contributor at all (rare, but happens), this is
the template to drop in. Replace `{Module}`, `{Tenant}`, `{Entity}`, and
adjust the namespace.

```csharp
using System;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Identity;
using Volo.Abp.MultiTenancy;
using Volo.Abp.PermissionManagement;
using Volo.Abp.Uow;
using Volo.Saas.Tenants;
using {Module}.Permissions;

namespace {Module}.Data;

/// <summary>
/// Seeds a demo tenant with an admin user and grants the application
/// permissions to its admin role. Idempotent.
/// </summary>
public class DemoTenantDataSeedContributor : IDataSeedContributor, ITransientDependency
{
    private const string DemoTenantName = "demo";

    private readonly ICurrentTenant _currentTenant;
    private readonly ITenantRepository _tenantRepository;
    private readonly TenantManager _tenantManager;
    private readonly IDataSeeder _dataSeeder;
    private readonly IIdentityRoleRepository _roleRepository;
    private readonly IPermissionManager _permissionManager;
    private readonly IUnitOfWorkManager _uowManager;
    private readonly ILogger<DemoTenantDataSeedContributor> _logger;

    public DemoTenantDataSeedContributor(/* inject all of the above */) { /* ... */ }

    [UnitOfWork]
    public virtual async Task SeedAsync(DataSeedContext context)
    {
        if (context?.TenantId != null) return;

        // Robust lookup — handles a previously-seeded tenant with any casing.
        var tenant = await _tenantRepository.FindByNameAsync(DemoTenantName);
        if (tenant == null)
        {
            var normalized = DemoTenantName.ToUpperInvariant();
            var existing = await _tenantRepository.GetListAsync();
            tenant = existing.FirstOrDefault(t => t.NormalizedName == normalized);
        }

        if (tenant == null)
        {
            tenant = await _tenantManager.CreateAsync(DemoTenantName);
            await _tenantRepository.InsertAsync(tenant, autoSave: true);
            _logger.LogInformation("Created tenant {TenantId}", tenant.Id);
        }

        using (_currentTenant.Change(tenant.Id, tenant.Name))
        {
            await _dataSeeder.SeedAsync(new DataSeedContext(tenant.Id)
                .WithProperty("AdminEmail", "admin@demo.io")
                .WithProperty("AdminPassword", "Admin1234!"));

            using (var uow = _uowManager.Begin(requiresNew: true))
            {
                var adminRole = await _roleRepository.FindByNormalizedNameAsync("ADMIN");
                if (adminRole != null)
                {
                    // Grant ALL feature permissions — keep this list in sync
                    // with the PermissionDefinitionProvider.
                    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.{Entity}.Default);
                    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.{Entity}.Create);
                    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.{Entity}.Edit);
                    await GrantIfMissingAsync(adminRole.Name, {Module}Permissions.{Entity}.Delete);
                }
                await uow.CompleteAsync();
            }
        }
    }

    private async Task GrantIfMissingAsync(string roleName, string permissionName)
    {
        var grant = await _permissionManager.GetForRoleAsync(roleName, permissionName);
        if (!grant.IsGranted)
        {
            await _permissionManager.SetForRoleAsync(roleName, permissionName, true);
        }
    }
}
```

## Checklist when finalizing a new feature

- [ ] Located the tenant data seed contributor (or noted it doesn't exist).
- [ ] Added `GrantIfMissingAsync` calls for the new
      `{Module}Permissions.{Entity}.Default/Create/Edit/Delete`.
- [ ] Ran `dotnet run --project {Host} -- --migrate-database` (or
      `./migrate-database.ps1`).
- [ ] Restarted the backend so the new `PermissionDefinitionProvider` is
      loaded into memory.
- [ ] Told the user to hard-refresh (Ctrl+F5) the React app.
