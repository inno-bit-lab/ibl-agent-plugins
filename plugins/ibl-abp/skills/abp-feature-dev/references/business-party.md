# Abstract base class for entities that share a field set

Most CRM / ERP projects have two or more entities whose field sets
converge: Customer / Supplier (most common), Lead / Customer,
Vendor / Subcontractor, AccountsPayable / AccountsReceivable. When the
shape is essentially the same, the right backend pattern is a single
abstract base.

Anchor example: **IBL360 `BusinessParty`** → Customer and Supplier.

## When to use it

All three hold:

- Two or more entities share ≥ 70% of their fields verbatim
  (identity, contact, address, financial, status).
- The lifecycle (status enum + transitions) is the same on both
  sides.
- The differences are countable on one hand (Customer has
  RelationshipType; Supplier has nothing extra). If divergence is
  bigger, the entities are different aggregates that happen to
  *look* similar — keep them separate.

If only one of these is true, don't unify yet. Premature inheritance
is at least as costly as duplication.

## C# pattern

```csharp
// Entities/Shared/BusinessParty.cs
public abstract class BusinessParty : AuditedAggregateRoot<Guid>, IMultiTenant
{
    public Guid? TenantId { get; set; }
    public string LegalName { get; set; } = string.Empty;
    public string DisplayName { get; set; } = string.Empty;
    // … every shared field …
    public PartyStatus Status { get; protected set; } = PartyStatus.Active;
    public DateTime? StatusChangedAt { get; protected set; }

    private static readonly Dictionary<PartyStatus, PartyStatus[]> AllowedTransitions = new()
    {
        [PartyStatus.Active]  = new[] { PartyStatus.OnHold, PartyStatus.Churned },
        [PartyStatus.OnHold]  = new[] { PartyStatus.Active, PartyStatus.Churned },
        [PartyStatus.Churned] = Array.Empty<PartyStatus>()
    };

    /// <summary>
    /// Subclasses provide their own error-code prefix so the same flow
    /// surfaces "Ibl360:Customers:InvalidStatusTransition" vs
    /// "Ibl360:Suppliers:InvalidStatusTransition" without duplicating
    /// the transition logic.
    /// </summary>
    protected abstract string InvalidStatusTransitionErrorCode { get; }

    public void ChangeStatus(PartyStatus newStatus, IClock clock)
    {
        if (newStatus == Status) return;
        if (!AllowedTransitions[Status].Contains(newStatus))
            throw new BusinessException(InvalidStatusTransitionErrorCode)
                .WithData("from", Status.ToString())
                .WithData("to", newStatus.ToString());

        Status = newStatus;
        StatusChangedAt = clock.Now;
    }

    protected BusinessParty() { }
    protected BusinessParty(Guid id, string legalName, string displayName,
                            PartySegment segment, Guid? tenantId = null)
        : base(id)
    {
        LegalName = Check.NotNullOrWhiteSpace(legalName, nameof(legalName), maxLength: 256);
        DisplayName = Check.NotNullOrWhiteSpace(displayName, nameof(displayName), maxLength: 128);
        Segment = segment;
        Status = PartyStatus.Active;
        TenantId = tenantId;
    }
}
```

```csharp
public class Customer : BusinessParty
{
    public RelationshipType RelationshipType { get; set; } = RelationshipType.Customer;

    protected Customer() { }
    public Customer(Guid id, string legalName, string displayName,
                    PartySegment segment, Guid? tenantId = null)
        : base(id, legalName, displayName, segment, tenantId) { }

    protected override string InvalidStatusTransitionErrorCode
        => Ibl360DomainErrorCodes.Customers.InvalidStatusTransition;
}

public class Supplier : BusinessParty
{
    protected Supplier() { }
    public Supplier(Guid id, string legalName, string displayName,
                    PartySegment segment, Guid? tenantId = null)
        : base(id, legalName, displayName, segment, tenantId) { }

    protected override string InvalidStatusTransitionErrorCode
        => Ibl360DomainErrorCodes.Suppliers.InvalidStatusTransition;
}
```

## Mongo persistence with this hierarchy

**Each concrete subclass has its own collection** (Customers,
Suppliers). NOT a single collection with a discriminator. Reasons:

- Permissions are per-collection (Ibl360.Customers vs
  Ibl360.Suppliers) and the auto API controllers expose distinct
  routes (`/api/app/customer`, `/api/app/supplier`).
- Indexes can diverge (Customer may want an extra index on
  RelationshipType; Supplier doesn't).
- Tenant isolation is identical on both sides — discriminator gives
  you nothing here.

The MongoDbContext registers each subclass independently:

```csharp
public IMongoCollection<Customer> Customers => Collection<Customer>();
public IMongoCollection<Supplier> Suppliers => Collection<Supplier>();

protected override void CreateModel(IMongoModelBuilder modelBuilder)
{
    base.CreateModel(modelBuilder);
    modelBuilder.Entity<Customer>(b => { b.CollectionName = "Customers"; });
    modelBuilder.Entity<Supplier>(b => { b.CollectionName = "Suppliers"; });
}
```

## Value objects with stable Ids in lists

When the parent contains a LIST of embedded VOs (multiple shipping
addresses, multiple bank accounts), and you also need a "default" or
"selected" pointer on the parent, **the pointer goes on the parent
referencing a stable Id on each VO** — NOT a flag on each VO.

```csharp
public class PostalAddress
{
    public Guid Id { get; set; }
    // …fields…
    public PostalAddress EnsureId()
    {
        if (Id == Guid.Empty) Id = Guid.NewGuid();
        return this;
    }
}

public abstract class BusinessParty
{
    public PostalAddress? BillingAddress { get; set; }
    public bool ShippingSameAsBilling { get; set; }
    public List<PostalAddress> ShippingAddresses { get; set; } = new();
    public Guid? DefaultShippingAddressId { get; set; }

    /// <summary>
    /// Reconcile shipping state. Call from the AppService after every
    /// Create/Update so the trio stays consistent:
    ///   - SameAsBilling=true  → list cleared, default null
    ///   - list empty          → default null
    ///   - list non-empty      → default must point to a member;
    ///                            otherwise promote the first item
    /// </summary>
    public void NormalizeShippingState()
    {
        if (ShippingSameAsBilling)
        {
            ShippingAddresses.Clear();
            DefaultShippingAddressId = null;
            return;
        }

        ShippingAddresses = ShippingAddresses
            .Where(a => !a.IsEmpty())
            .Select(a => a.EnsureId())
            .ToList();

        if (ShippingAddresses.Count == 0)
        {
            DefaultShippingAddressId = null;
            return;
        }

        if (!DefaultShippingAddressId.HasValue ||
            !ShippingAddresses.Any(a => a.Id == DefaultShippingAddressId.Value))
        {
            DefaultShippingAddressId = ShippingAddresses[0].Id;
        }
    }
}
```

Why on the parent and not a flag on each address:

- **No "multiple defaults" bug**: there's exactly one pointer, by
  construction.
- **No cleanup on delete**: removing an address doesn't require
  scanning for "the next one to be default" — the AppService just
  calls `NormalizeShippingState()`.
- **Cleaner BSON**: addresses don't carry a `IsDefault` flag that
  has to be maintained in sync with siblings.

The corresponding UI pattern (radio-toggle that calls a "make
default" action on the parent) is documented in
`abp-react-ui/references/complex-edit-page.md`.

## Closed enums for closed sets

Free-text strings ("LinkedIn", "Twitter", "Facebook") in a list field
are wrong twice over: the UI can't render an icon reliably, and the
data drifts ("Linked-In", "linkedin", "LI"). Use a closed enum with
matching frontend icons.

```csharp
public enum SocialPlatform
{
    LinkedIn,
    Twitter,
    Facebook,
    Instagram,
    YouTube,
    GitHub,
    Website,
    Other
}

public class SocialLink
{
    public SocialPlatform Platform { get; set; } = SocialPlatform.Website;
    public string Url { get; set; } = string.Empty;
}
```

Stored as string in BSON (already configured globally in IBL360
via `EnumRepresentationConvention(BsonType.String)`). The TS side
gets a string-literal union, the React side maps each value to a
lucide-react icon in a metadata table.

If the set might grow beyond what icons can fit (40+ values),
consider keeping it open as a string — but then the UI is forced
to a single icon for everyone and the value drifts. The bar to
keep it open is high.

## DTO mirroring

Two base DTO classes mirror the entity hierarchy:

```csharp
public abstract class BusinessPartyDtoBase : AuditedEntityDto<Guid>
{
    // every shared field as get/set
}

public abstract class BusinessPartyCreateUpdateDtoBase
{
    // every shared field with validation attributes
}

public class CustomerDto : BusinessPartyDtoBase
{
    public RelationshipType RelationshipType { get; set; }
}

public class CreateUpdateCustomerDto : BusinessPartyCreateUpdateDtoBase
{
    [Required] public RelationshipType RelationshipType { get; set; }
}

// SupplierDto / CreateUpdateSupplierDto are empty subclasses.
```

## Push the abstraction up the whole stack

Once the entity has a BusinessParty base, every other layer that
operates on it has the same opportunity. Don't stop at the entity —
the AppService, its interface, the list-input DTO, and (when needed)
the repository all benefit from the same generic-base treatment.

The IBL360 codebase is the reference: every layer below carries a
shared base. Concrete Customer/Supplier classes are deliberately thin
— their job is to bind the generics and provide hooks for the few
fields that diverge.

```
              BusinessParty (abstract entity)
                       │
            ┌──────────┴───────────┐
        Customer                Supplier         ← concrete aggregates
            │                       │
   BusinessPartyDtoBase     BusinessPartyDtoBase
            │                       │
       CustomerDto             SupplierDto       ← read-side
            │                       │
   BusinessPartyCreateUpdateDtoBase (shared)
            │                       │
 CreateUpdateCustomerDto   CreateUpdateSupplierDto
            │                       │
       PartyListInputBase (shared)
            │                       │
   GetCustomersInput            GetSuppliersInput

         IBusinessPartyAppService<TDto, TCreateUpdate, TGetInput>
                       │
            ┌──────────┴───────────┐
   ICustomerAppService        ISupplierAppService   ← contracts

   BusinessPartyAppServiceBase<TEntity, TDto, TCreateUpdate, TGetInput>
                       │
            ┌──────────┴───────────┐
      CustomerAppService       SupplierAppService   ← concrete services
```

### 1. The mapping helper (data → entity)

A pure static helper centralizes the field-by-field copy from DTO to
aggregate. This is the lowest-effort piece of the stack:

```csharp
// Services/Shared/BusinessPartyMapping.cs
public static class BusinessPartyMapping
{
    public static void ApplyTo(BusinessParty party, BusinessPartyCreateUpdateDtoBase input)
    {
        party.TaxId = NormalizeTaxId(input.TaxId);
        // …every shared field…
        party.NormalizeShippingState();  // ALWAYS at the end
    }

    // private helpers for normalizing addresses, socials, custom fields
}
```

### 2. The list-input base

The Get*Input DTOs of both entities share the same filter set (free
text, status, segment, country, date range). Lift it once:

```csharp
public abstract class PartyListInputBase : PagedAndSortedResultRequestDto
{
    public string? Filter { get; set; }
    public PartyStatus? Status { get; set; }
    public PartySegment? Segment { get; set; }
    public string? Country { get; set; }
    public DateTime? CreatedFrom { get; set; }
    public DateTime? CreatedTo { get; set; }
}

public class GetCustomersInput : PartyListInputBase
{
    public RelationshipType? RelationshipType { get; set; }
}

public class GetSuppliersInput : PartyListInputBase { }
```

### 3. The interface base

```csharp
public interface IBusinessPartyAppService<TDto, TCreateUpdate, TGetInput>
    : ICrudAppService<TDto, Guid, TGetInput, TCreateUpdate>
    where TDto : IEntityDto<Guid>
    where TGetInput : PartyListInputBase
{
    Task<TDto> ChangeStatusAsync(Guid id, ChangePartyStatusDto input);
}

public interface ICustomerAppService
    : IBusinessPartyAppService<CustomerDto, CreateUpdateCustomerDto, GetCustomersInput>
{
    // no extra endpoints — RelationshipType travels inside the existing DTOs
}

public interface ISupplierAppService
    : IBusinessPartyAppService<SupplierDto, CreateUpdateSupplierDto, GetSuppliersInput>
{ }
```

The `ChangeStatusAsync` parameter is a shared `ChangePartyStatusDto`
(carrying `PartyStatus`) — one DTO, not two per-entity copies.

### 4. The AppService base (the centerpiece)

```csharp
public abstract class BusinessPartyAppServiceBase<TEntity, TDto, TCreateUpdate, TGetInput>
    : ApplicationService,
      IBusinessPartyAppService<TDto, TCreateUpdate, TGetInput>
    where TEntity : BusinessParty
    where TDto : class, IEntityDto<Guid>
    where TCreateUpdate : BusinessPartyCreateUpdateDtoBase
    where TGetInput : PartyListInputBase
{
    protected readonly IRepository<TEntity, Guid> Repository;

    protected BusinessPartyAppServiceBase(IRepository<TEntity, Guid> repository)
        => Repository = repository;

    // The full CRUD surface lives here as `virtual` methods. Subclasses
    // override only the per-entity bits via the hooks below.

    public virtual async Task<TDto> GetAsync(Guid id) { /* ... */ }
    public virtual async Task<PagedResultDto<TDto>> GetListAsync(TGetInput input) { /* ... */ }
    public virtual async Task<TDto> CreateAsync(TCreateUpdate input) { /* ... */ }
    public virtual async Task<TDto> UpdateAsync(Guid id, TCreateUpdate input) { /* ... */ }
    public virtual async Task DeleteAsync(Guid id) { /* ... */ }
    public virtual async Task<TDto> ChangeStatusAsync(Guid id, ChangePartyStatusDto input) { /* ... */ }

    /* Hooks subclasses implement */
    protected abstract TEntity CreateEntity(TCreateUpdate input);
    protected abstract TDto MapToDto(TEntity entity);
    protected virtual void ApplyEntitySpecificFields(TEntity entity, TCreateUpdate input) { }
    protected virtual IQueryable<TEntity> ApplyEntityFilters(IQueryable<TEntity> q, TGetInput input) => q;
    protected virtual string DefaultSorting => nameof(BusinessParty.LegalName);

    /* Shared filter logic — free-text search, Status/Segment/Country range */
    private IQueryable<TEntity> ApplyBaseFilters(IQueryable<TEntity> q, TGetInput input)
    {
        // free text on LegalName/DisplayName/TaxId/FiscalCode/
        //   PrimaryContactName/Email
        // Status, Segment, Country (nested BillingAddress.Country), date range
    }
}
```

The full implementation is in
`Services/Shared/BusinessPartyAppServiceBase.cs` — copy verbatim,
tweak the search columns if your entity has different identifying
fields.

### 5. The concrete AppService

The Customer side reduces to ~80 lines from ~180:

```csharp
[Authorize(Ibl360Permissions.Customers.Default)]
public class CustomerAppService
    : BusinessPartyAppServiceBase<Customer, CustomerDto, CreateUpdateCustomerDto, GetCustomersInput>,
      ICustomerAppService
{
    public CustomerAppService(IRepository<Customer, Guid> repository) : base(repository) { }

    /* ------------ Hooks ------------ */

    protected override Customer CreateEntity(CreateUpdateCustomerDto input)
        => new(GuidGenerator.Create(),
               input.LegalName, input.DisplayName, input.Segment, CurrentTenant.Id);

    protected override CustomerDto MapToDto(Customer entity)
        => ObjectMapper.Map<Customer, CustomerDto>(entity);

    protected override void ApplyEntitySpecificFields(Customer e, CreateUpdateCustomerDto input)
        => e.RelationshipType = input.RelationshipType;

    protected override IQueryable<Customer> ApplyEntityFilters(
        IQueryable<Customer> q, GetCustomersInput input)
        => input.RelationshipType.HasValue
            ? q.Where(c => c.RelationshipType == input.RelationshipType.Value)
            : q;

    /* ------------ Authorize redeclarations (forward to base) ------------ */

    public override Task<CustomerDto> GetAsync(Guid id) => base.GetAsync(id);
    public override Task<PagedResultDto<CustomerDto>> GetListAsync(GetCustomersInput input)
        => base.GetListAsync(input);

    [Authorize(Ibl360Permissions.Customers.Create)]
    public override Task<CustomerDto> CreateAsync(CreateUpdateCustomerDto input)
        => base.CreateAsync(input);

    [Authorize(Ibl360Permissions.Customers.Edit)]
    public override Task<CustomerDto> UpdateAsync(Guid id, CreateUpdateCustomerDto input)
        => base.UpdateAsync(id, input);

    [Authorize(Ibl360Permissions.Customers.Delete)]
    public override Task DeleteAsync(Guid id) => base.DeleteAsync(id);

    [Authorize(Ibl360Permissions.Customers.Edit)]
    public override Task<CustomerDto> ChangeStatusAsync(Guid id, ChangePartyStatusDto input)
        => base.ChangeStatusAsync(id, input);
}
```

Supplier is even smaller (~55 lines) because it has no entity-specific
fields or filters; it only redeclares the [Authorize] attributes.

### Why the [Authorize] forwarding boilerplate is non-negotiable

**ABP's auto API controllers do NOT inherit attributes from generic
base methods.** The reflective scanning that exposes `/api/app/customer/*`
endpoints only sees attributes on the most-derived declaration of each
public method. If you put `[Authorize(...)]` on the base CreateAsync,
the generated controller endpoint has no `[Authorize]` and anonymous
requests succeed.

This is also why the per-entity permission constants must be reachable
from a concrete declaration — the base can't pick the right one. The
~10-line forwarding override block is annoying but it's the smallest
honest version: explicit, greppable, attribute-visible.

### Repositories: generic ABP is usually enough

You'll be tempted to add an `IBusinessPartyRepository<TEntity>` mirror.
**Resist unless you have a specific reason.** ABP's
`IRepository<TEntity, Guid>` already provides:

- `GetAsync(id)`, `InsertAsync`, `UpdateAsync`, `DeleteAsync`
- `GetQueryableAsync()` for LINQ
- All the multi-tenancy + soft-delete filters

The custom-repository pattern in ABP is for **typed filter methods**
that can't be expressed cleanly in LINQ at the AppService layer
(e.g. `FindByCustomerCodeAsync(string code, params Status[] statuses)`
where the same query repeats in 5 places).

If your BusinessParty has such methods, write:

```csharp
public interface IBusinessPartyRepository<TEntity> : IRepository<TEntity, Guid>
    where TEntity : BusinessParty
{
    Task<TEntity?> FindByLegalNameAsync(string legalName, CancellationToken ct = default);
}

// concrete:
public interface ICustomerRepository : IBusinessPartyRepository<Customer> { }
```

And the Mongo implementation in `Data/{Plural}/Mongo{Entity}Repository.cs`
inheriting from `MongoDbRepository<Ibl360DbContext, TEntity, Guid>`.

Until then, take the generic repo. It's not duplication you're saving;
it's empty boilerplate.

### What this generic-base pattern explicitly DOES NOT solve

- **Different lifecycle methods**: if Customer has `ChangeSegment` and
  Supplier doesn't, you can't generic-base that. Subclass it on the
  side that has it; don't pollute the base with optional methods.
- **Different validation paths**: if Customer's Update has a
  cross-field check that Supplier doesn't, the override of UpdateAsync
  is the right place — call `base.UpdateAsync` AFTER the check.
- **Different audit / event behavior**: if Customer raises a
  `CustomerStatusChanged` event but Supplier doesn't, override
  `ChangeStatusAsync` on the Customer side. The base method stays
  generic.

### Line-count payoff (IBL360 numbers)

| File | Before generic base | After generic base |
|---|---|---|
| `CustomerAppService.cs` | ~180 lines | ~80 lines |
| `SupplierAppService.cs` | ~190 lines | ~55 lines |
| `CustomerAppService` unique surface | ~20 lines | ~20 lines |
| `SupplierAppService` unique surface | ~0 lines | ~0 lines |

The unique-surface line counts are the meaningful ones. Adding a third
entity (Lead, Vendor) brings them to ~20 + ~0 + ~10 — the marginal
cost approaches the actual divergence between aggregates.

## Mongo index migration when fields move into a VO

When a refactor moves a top-level field into a nested VO (e.g.
`Country` → `BillingAddress.Country`), the old index on the flat
path becomes stale: same name, different shape. The
`IDataSeedContributor` that owns the index must:

1. **Drop the legacy index by name** (try/catch
   `MongoCommandException` so the first run on a fresh DB doesn't
   fail).
2. **Recreate** with the new key path
   (`Builders<T>.IndexKeys.Ascending("BillingAddress.Country")` — the
   string form works for nested paths).

See `references/data-migration.md` for the full migration playbook
including BSON document migration when the schema changes.

## Localization unification

`PartyStatus.*` and `PartySegment.*` get their own keys
(`Enum:PartyStatus.Active`, etc.). Keep the old per-entity keys
(`Enum:CustomerStatus.Active`) **for one release** so any cached
client doesn't render raw keys; you can drop them once everyone
has refreshed.

## Data migration is NOT optional when this pattern is introduced

Introducing a BusinessParty base usually involves enum unification
(CustomerStatus + SupplierStatus → PartyStatus). If the old enums had
values the new one doesn't (Prospect → moved to RelationshipType), and
any existing document carries those values, **the read endpoint
returns HTTP 500 with a `FormatException` from the BSON deserializer.**
The error is invisible at build/restart time and only fires when a
list query hits a document with the removed value.

Before declaring the refactor done, run the mandatory checklist from
`data-migration.md`. The IBL360 refactor missed this and the bug
landed in production-grade dev — symptom was
`GET /api/app/supplier → 500`, with the inner exception
`Requested value 'Prospect' was not found`.

Mandatory sweep after unifying Customer/Supplier enums:

```js
// 1. Remap removed values
db.Customers.updateMany({ Status: "Prospect" },
  { $set: { Status: "Active", RelationshipType: "Prospect" } })
db.Suppliers.updateMany({ Status: "Prospect" },
  { $set: { Status: "Active" } })

// 2. Default the newly added required field on legacy docs
db.Customers.updateMany({ RelationshipType: { $exists: false } },
  { $set: { RelationshipType: "Customer" } })

// 3. Strip flat fields moved into VOs
db.Customers.updateMany(
  { $or: [{ Country: { $exists: true } }, { Address: { $exists: true } }] },
  { $unset: { Country: "", Address: "" } })
db.Suppliers.updateMany(
  { $or: [{ Country: { $exists: true } }, { Address: { $exists: true } }] },
  { $unset: { Country: "", Address: "" } })

// 4. Sanity sweep — all must return 0
db.Customers.countDocuments({ Status: { $nin: ["Active", "OnHold", "Churned"] } })
db.Suppliers.countDocuments({ Status: { $nin: ["Active", "OnHold", "Churned"] } })
db.Customers.countDocuments({ RelationshipType: { $exists: false } })
db.Customers.countDocuments({ Country: { $exists: true } })
db.Suppliers.countDocuments({ Country: { $exists: true } })
```

For a fresh DB on a colleague's machine, the same sweep runs but the
counts are 0 from the start. The cost of running it on a clean DB is
~10ms. The cost of skipping it on a dev DB is a 500-error session.

## What this pattern explicitly DOES NOT solve

- **Distinct lifecycles**: if Customer has Prospect/Active/Churned
  and Supplier has Active/OnHold/Discontinued, the abstraction
  leaks. Keep separate enums and don't unify.
- **Different permission models**: if Customer is a tenant-only
  resource and Supplier is host-managed, the unification adds
  zero value — they're different in the dimension that matters
  most.
- **Wildly different validation**: if Customer requires
  TaxId-or-FiscalCode-not-both and Supplier requires neither,
  the validation logic doesn't share — and you'll end up with
  conditionals in `BusinessPartyMapping.ApplyTo` that betray the
  abstraction.

Three concrete entities with the SAME field set, lifecycle, and
permission shape: that's the green light.
