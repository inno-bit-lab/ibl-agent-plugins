---
name: abp-multitenancy
description: 'ABP Framework multi-tenancy - making entities tenant-aware via IMultiTenant, accessing CurrentTenant, switching tenant context with CurrentTenant.Change, bypassing the multi-tenant data filter, tenant resolution strategies, and host vs tenant behavior. Use to add multi-tenancy to an entity, query across tenants, switch tenant or host context, configure tenant resolution, define permissions per tenancy side, or troubleshoot tenant-filter visibility issues. Triggers on IMultiTenant, TenantId, CurrentTenant, multi-tenant, switch tenant, data filter, DataFilter.Disable, or tenant resolver.'
---

# ABP Multi-Tenancy

ABP's multi-tenancy is opt-in per entity. When an entity implements
`IMultiTenant`, ABP **automatically**:

- Sets `TenantId = CurrentTenant.Id` on insert.
- Filters every repository query by `TenantId == CurrentTenant.Id`.
- Refuses to leak data between tenants — even when bugs would otherwise expose it.

The whole subsystem rests on this contract; understanding it makes the rest of
the design obvious.

## Making an entity tenant-aware

```csharp
public class Product : AggregateRoot<Guid>, IMultiTenant
{
    public Guid? TenantId { get; set; }   // nullable; required by IMultiTenant

    public string Name { get; private set; }
    public decimal Price { get; private set; }

    protected Product() { }

    public Product(Guid id, string name, decimal price) : base(id)
    {
        Name  = name;
        Price = price;
        // TenantId is set automatically on insert from CurrentTenant.Id
    }
}
```

Key things to remember:
- `TenantId` is **nullable**. `null` means *"owned by the host (root admin)"*,
  not *"all tenants."* A host-owned record is invisible to tenants and vice
  versa unless the filter is disabled.
- The property has a **public setter** intentionally — ABP needs to assign
  it during insert. The setter is the one exception to the "private setters
  everywhere" rule for rich entities.
- Don't manually filter by `TenantId` in your queries. The data filter does
  it for you, and writing it by hand both clutters the query and breaks if
  the filter is later disabled.
- Don't change `TenantId` after creation — that moves the record between
  tenants. If you must, do it explicitly in a host-side maintenance script.

### Adding IMultiTenant to an existing entity

```bash
# Interactive
python <skills-root>/abp-multitenancy/scripts/add_multitenant_to_entity.py

# Scripted
python <skills-root>/abp-multitenancy/scripts/add_multitenant_to_entity.py \
    --entity-file src/MyProject/Books/Book.cs
```

The script:
1. Adds `using Volo.Abp.MultiTenancy;` if missing.
2. Appends `, IMultiTenant` to the class declaration (or adds `: IMultiTenant`
   if there's no base list).
3. Inserts `public Guid? TenantId { get; set; }` at the top of the class body.
4. Is **idempotent** — reports `[skip]` if already done.

⚠ The script does NOT migrate existing data. Existing records get `NULL`
TenantId (= host-owned). If you intend to assign them to a tenant, run a
one-off update separately.

## Accessing the current tenant

In any class inheriting from an ABP base class, `CurrentTenant` is already a
property — no injection needed:

```csharp
public class ProductAppService : ApplicationService
{
    public void Describe()
    {
        var id          = CurrentTenant.Id;            // Guid? — null = host
        var name        = CurrentTenant.Name;          // string?
        var isAvailable = CurrentTenant.IsAvailable;   // true iff Id != null
    }
}
```

In plain services, inject `ICurrentTenant`:

```csharp
public class MyHelper : ITransientDependency
{
    public MyHelper(ICurrentTenant currentTenant) => _currentTenant = currentTenant;
}
```

## Switching tenant context

`CurrentTenant.Change(tenantId)` returns an `IDisposable` that temporarily
switches the ambient tenant. Always use it inside a `using` block — when the
block exits, the previous tenant is restored.

```csharp
public class HostOnlyJob : ApplicationService
{
    public async Task<long> CountForAsync(Guid? tenantId)
    {
        using (CurrentTenant.Change(tenantId))
        {
            return await _productRepo.GetCountAsync();
        }
    }

    public async Task DoSomethingAsHostAsync()
    {
        using (CurrentTenant.Change(null))   // host context
        {
            // ...
        }
    }
}
```

This is the pattern for **host-side background work** that needs to operate
inside multiple tenants — e.g. nightly report generation, bulk imports.

## Bypassing the multi-tenant filter

To run a single query across **all tenants** (e.g. a host-side aggregate
report), disable the filter for the duration of one block:

```csharp
public async Task<long> CountAcrossAllTenantsAsync()
{
    using (DataFilter.Disable<IMultiTenant>())
    {
        return await _productRepo.GetCountAsync();
    }
}
```

Caveats:
- This **only works with a single database**. If each tenant has its own
  database (the "database-per-tenant" model), disabling the filter doesn't
  give you visibility into the other databases — you'd need to switch the
  connection string per tenant.
- Be very deliberate about where this lives. It's a sharp tool; misuse leaks
  data between tenants.

## Database architecture

| Pattern | Description | When |
|---|---|---|
| Single database | All tenants share one DB; rows filtered by `TenantId` | Default; simplest; lowest cost |
| Database per tenant | Each tenant has its own DB | Strong isolation, compliance, premium tier |
| Hybrid | Some tenants share, others isolated | Mix of plans |

Connection strings are managed in the Tenant Management module — each
tenant record can carry its own connection string that ABP picks up
automatically.

## Tenant resolution

ABP picks the current tenant from the request in this priority order:

1. The authenticated user's claims (`tenantid`).
2. Query string: `?__tenant=...`.
3. Route token: `/{__tenant}/...`.
4. HTTP header: `__tenant`.
5. Cookie: `__tenant`.
6. Domain / subdomain (if configured).

For subdomain-based resolution:

```csharp
Configure<AbpTenantResolveOptions>(options =>
{
    options.AddDomainTenantResolver("{0}.mydomain.com");
});
```

Order the resolvers by reliability — claim-based wins because it's signed
into the JWT.

## Permissions per tenancy side

**Rule of thumb**: if the entity is `IMultiTenant`, its permissions should
default to `MultiTenancySides.Tenant` — host admins shouldn't see "Manage
Customers" on the tenant-scoped Customers entity. That's clutter at best
and a footgun at worst (the action would either fail under the multi-tenant
filter or, if the filter is disabled, leak data across tenants).

```csharp
var customersPermission = myGroup.AddPermission(
    {{ROOT_NAMESPACE}}Permissions.Customers.Default,
    L("Permission:Customers"),
    MultiTenancySides.Tenant);

customersPermission.AddChild(
    {{ROOT_NAMESPACE}}Permissions.Customers.Create,
    L("Permission:Customers.Create"),
    MultiTenancySides.Tenant);
// ... same for Edit, Delete
```

Options: `MultiTenancySides.Host`, `Tenant`, `Both` (default). Use:
- **`Tenant`** — for every entity scoped to a tenant (the default for any
  `IMultiTenant` entity).
- **`Host`** — for cross-tenant reporting, tenant provisioning, platform
  configuration.
- **`Both`** — for genuinely shared resources like a global lookup table
  that both host admins and tenants can see.

The `abp-feature-dev` scaffolder's permission snippet uses
`MultiTenancySides.Tenant` automatically when the interview chose
`--multi-tenant yes`.

## Tenant-aware unique constraints

When porting a SQL `UNIQUE` constraint to a multi-tenant Mongo entity, a
single-field unique index is **wrong** — it prevents two tenants from
having the same value (e.g. two tenants couldn't both have a customer with
`TaxId = "ABC"`).

Use a compound `(TenantId, Field)` unique index. For MongoDB:

```csharp
await col.Indexes.CreateOneAsync(new CreateIndexModel<Customer>(
    Builders<Customer>.IndexKeys
        .Ascending(c => c.TenantId)
        .Ascending(c => c.TaxId),
    new CreateIndexOptions<Customer>
    {
        Unique = true,
        PartialFilterExpression = Builders<Customer>.Filter.Ne(c => c.TaxId, null),
        Name = "TenantId_TaxId_unique"
    }));
```

For EF Core:

```csharp
modelBuilder.Entity<Customer>()
    .HasIndex(c => new { c.TenantId, c.TaxId })
    .IsUnique()
    .HasFilter("[TaxId] IS NOT NULL");
```

The same applies to **email**, **username**, **code**, or any other "unique
within tenant" field. The `abp-mongodb` skill has more on the MongoDB
index syntax.

## Host-side maintenance pattern

For one-off host-side work that needs to touch multiple tenants
(migrations, bulk imports, cross-tenant reports), use `CurrentTenant.Change`
to scope each operation:

```csharp
public class CustomerImportJob : ApplicationService
{
    public async Task ImportForAllTenantsAsync()
    {
        var tenantIds = await GetAllTenantIdsAsync();
        foreach (var tenantId in tenantIds)
        {
            using (CurrentTenant.Change(tenantId))
            {
                // All repository calls here see only this tenant's data
                await _customerImporter.RunAsync();
            }
        }
    }
}
```

Avoid `DataFilter.Disable<IMultiTenant>()` for this kind of work — it's
too easy to leak state across the loop iterations.

## Enabling / disabling multi-tenancy globally

```csharp
Configure<AbpMultiTenancyOptions>(options =>
{
    options.IsEnabled = true;   // default in ABP templates
});
```

If you disable it, `IMultiTenant` becomes a no-op — `TenantId` stays nullable
but the filter doesn't run. Centralize this via
`MultiTenancyConsts.IsEnabled` in your solution so it's a single source of
truth.

## Common pitfalls

- **"Why don't I see this record?"** — Check the current tenant. The most
  common symptom of "my query returns empty" in an ABP project is running it
  in the wrong tenant context.
- **Forgetting `IMultiTenant` on a sibling entity.** If `Order` is
  multi-tenant but `OrderLine` (child of Order) is not, you've leaked the
  child across tenants. Children of a multi-tenant aggregate root should
  themselves be multi-tenant — or be embedded so they never query
  independently.
- **Hardcoding tenant IDs in queries.** Don't. Trust the filter; use
  `Change()` if you need a different scope.
- **Disabling the filter "to debug something" and forgetting to remove it.**
  Always inside a `using` block, never globally.
