---
name: abp-core
description: 'Core ABP Framework knowledge for .NET projects: module system, dependency injection, base classes, audit entities, BusinessException with localized DomainErrorCodes, ConcurrencyStamp, localization, soft delete, multi-tenancy basics, and common anti-patterns. Use whenever the user works on ABP modules, ApplicationService, AggregateRoot, IRepository, IClock, CurrentUser, GuidGenerator, ITransientDependency, auto API controllers, or when another abp-* skill needs shared project detection through abp_context.py. Trigger on any ABP-specific work.'
---

# ABP Framework — Core conventions

> Official docs: <https://abp.io/docs/latest>
> API reference: <https://abp.io/docs/api/>

This skill is the **entry point** for any work on an ABP Framework project. It
covers the conventions that apply everywhere (modules, DI, base classes,
audit/persistence shape, exceptions, async, time, anti-patterns) and hosts the
shared `scripts/abp_context.py` module that other `abp-*` skills import for
project detection and placeholder resolution.

## Project context (read first)

Before generating or modifying ABP code, resolve the project context so
generated files use the right names, namespaces, and paths.

```bash
python <skills-root>/abp-core/scripts/abp_context.py
# Prints JSON like:
# {
#   "project_name": "MyProject",
#   "root_namespace": "MyProject",
#   "template_type": "nolayers",
#   "data_provider": "mongodb",
#   "project_root": "src/MyProject",
#   "solution_root": "C:/path/to/solution"
# }
```

Other `abp-*` skills import this module:

```python
import sys, os
sys.path.insert(0, os.path.expanduser('<skills-root>/abp-core/scripts'))
from abp_context import load_or_prompt_config, resolve_placeholders

ctx = load_or_prompt_config()
code = resolve_placeholders(template_text, ctx)
```

Supported placeholders: `{{PROJECT_NAME}}`, `{{ROOT_NAMESPACE}}`,
`{{TEMPLATE_TYPE}}`, `{{DATA_PROVIDER}}`, `{{PROJECT_ROOT}}`, `{{SOLUTION_ROOT}}`.

## Module system

Every ABP application or library is an `AbpModule` that declares its
dependencies and configures services.

```csharp
[DependsOn(
    typeof(AbpDddDomainModule),
    typeof(AbpAutoMapperModule)
)]
public class {{PROJECT_NAME}}Module : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        // Register services, options, etc.
    }
}
```

Middleware configuration (`OnApplicationInitialization`) belongs only in the
**final host application**, not in reusable modules.

To validate an existing module file:

```bash
python <skills-root>/abp-core/scripts/validate_module.py \
    --module-path src/MyProject/MyProjectModule.cs
```

## Dependency injection — three rules

1. **Mark, don't register.** Implement `ITransientDependency`,
   `IScopedDependency`, or `ISingletonDependency` instead of calling
   `services.AddX<T>(...)`.
2. **Base classes are auto-registered.** `ApplicationService`,
   `DomainService`, `AbpController`, `Profile` — don't add a marker interface.
3. **Use the generic repository for plain CRUD.** Define a custom
   `IXyzRepository : IRepository<Xyz, TKey>` only when you need named query
   methods or share a filter chain across endpoints. See the `abp-mongodb`
   skill for the custom repo pattern.

```csharp
[ExposeServices(typeof(IMyService))]
public class MyService : IMyService, ITransientDependency { }
```

## Base classes & the "check before injecting" rule

ABP base classes expose the services you'd otherwise inject 90% of the time.
**Before adding a constructor parameter, check whether the property already
exists** — injecting `IClock` into an `ApplicationService` is redundant
because `Clock` is already a property.

For the full table of base classes and the properties they provide, see
**references/base-classes.md**.

The most commonly used properties:

- `Clock` (all base classes) — use instead of `DateTime.Now/UtcNow`
- `CurrentUser` (all) — `.Id`, `.UserName`, `.Email`, `.TenantId`,
  `.IsAuthenticated`, `.Roles`
- `CurrentTenant` (all) — multi-tenancy context, including
  `CurrentTenant.Change(tenantId)` for `using`-scoped switching
- `GuidGenerator` (all) — `Create()` returns a new Guid
- `L` (`ApplicationService`, `AbpController`) — `L["MyKey"]` localization
- `DataFilter` (all) — toggle soft-delete / multi-tenant filters with `using`

Useful methods:

- `CheckPolicyAsync(permission)` — throws if not granted
- `IsGrantedAsync(permission)` — returns bool, never throws

## Choosing the entity base class

ABP exposes a ladder of base classes; pick the lowest rung that gives you
what you need. The choice impacts auditing, soft-delete behavior, and the
shape of every endpoint that touches the entity.

| Base | Adds | When to pick |
|---|---|---|
| `Entity<TKey>` | nothing | Trivial value-object-like records, no audit needed |
| `AggregateRoot<TKey>` | Domain events | DDD aggregates with no audit requirements |
| `AuditedAggregateRoot<TKey>` | `CreationTime`, `CreatorId`, `LastModificationTime`, `LastModifierId` | **Default for most CRUD entities.** Cheap, useful, expected by admin tooling. |
| `FullAuditedAggregateRoot<TKey>` | + `DeleterId`, `DeletionTime`, `IsDeleted` (soft delete) | Records that should never be hard-deleted (legal, financial, audit), or where accidental delete is a real risk and you want a recycle bin |

**Soft delete** is implicit with `FullAuditedAggregateRoot` — `DeleteAsync`
sets `IsDeleted = true` and queries filter it out automatically. To see
deleted rows for an admin "recycle bin":

```csharp
using (DataFilter.Disable<ISoftDelete>())
{
    var deleted = await _repository.GetListAsync(c => c.IsDeleted);
}
```

To restore: load via the bypassed filter, set `IsDeleted = false`,
`UpdateAsync`.

Don't pick `FullAudited` "just in case" — soft delete complicates many
queries (joins, aggregates, uniqueness constraints) and most teams
underestimate the cost.

## ConcurrencyStamp — optimistic locking

If the entity is edited by many users with long edit sessions and the cost
of a lost update is high, mark it `IHasConcurrencyStamp`:

```csharp
public class Customer : AuditedAggregateRoot<Guid>, IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; } = default!;
    // …
}
```

The output DTO carries the current stamp; the client passes it back on
update; the AppService verifies and updates atomically:

```csharp
public async Task<CustomerDto> UpdateAsync(Guid id, UpdateCustomerDto input)
{
    var customer = await _repository.GetAsync(id);
    customer.SetConcurrencyStampIfNotNull(input.ConcurrencyStamp);
    customer.Update(/* … */);
    await _repository.UpdateAsync(customer);
    return ObjectMapper.Map<Customer, CustomerDto>(customer);
}
```

ABP throws `AbpDbConcurrencyException` (HTTP 409 by default) when stamps
mismatch.

For most admin CRUD, **skip it** — the cost is a stamp the client must
round-trip and a 409 to handle. Add it only when you have a real concurrency
problem.

## Async, the right way

- Async all the way — never `.Result` or `.Wait()`.
- Suffix async method names with `Async`.
- ABP propagates `CancellationToken` automatically. Add a `CancellationToken`
  parameter only when you need to layer custom cancellation logic on top.

## Time — never `DateTime.Now`

```csharp
// ❌ Not testable, ignores ABP's timezone configuration
var ts = DateTime.UtcNow;

// ✅ Inside a base class
var ts = Clock.Now;

// ✅ Elsewhere — inject IClock
public class MyHelper : ITransientDependency
{
    public MyHelper(IClock clock) => _clock = clock;
}

// ✅ Inside a non-base-class entity — accept IClock as method parameter
public void ChangeStatus(CustomerStatus newStatus, IClock clock)
{
    // …
    StatusChangedAt = clock.Now;
}
```

The pattern of "accept `IClock` as a method parameter" is what lets entities
remain testable without inheriting from an ABP base class.

## Business exceptions and the DomainErrorCodes pattern

Throw `BusinessException` (or a specialization) with a namespaced error
code. Codes are easier to grep, easier to localize, and easier to map to
HTTP status when grouped under a static class:

```csharp
// One file at the project root: {{PROJECT_NAME}}DomainErrorCodes.cs
namespace {{ROOT_NAMESPACE}};

public static class {{ROOT_NAMESPACE}}DomainErrorCodes
{
    public static class Customers
    {
        public const string InvalidStatusTransition = "{{ROOT_NAMESPACE}}:Customers:InvalidStatusTransition";
        public const string InvalidCountryCode      = "{{ROOT_NAMESPACE}}:Customers:InvalidCountryCode";
        public const string InvalidFiscalCode       = "{{ROOT_NAMESPACE}}:Customers:InvalidFiscalCode";
    }
}

// In the entity:
throw new BusinessException({{ROOT_NAMESPACE}}DomainErrorCodes.Customers.InvalidStatusTransition)
    .WithData("From", Status)
    .WithData("To", newStatus);
```

Map the namespace to a localization resource so the message is shown to
the user in their language:

```csharp
Configure<AbpExceptionLocalizationOptions>(options =>
{
    options.MapCodeNamespace("{{ROOT_NAMESPACE}}", typeof({{PROJECT_NAME}}Resource));
});
```

In each language file:

```json
"{{ROOT_NAMESPACE}}:Customers:InvalidStatusTransition":
    "Transizione di stato non valida da {From} a {To}."
```

The `{From}` / `{To}` placeholders come from the `.WithData(...)` calls.

Specialized exceptions: `EntityNotFoundException`, `UserFriendlyException`,
`AbpValidationException`, `AbpAuthorizationException`,
`AbpDbConcurrencyException`. HTTP mapping is configurable — don't rely on
defaults in business logic.

## Localization

- Inside a base class: `L["MyKey"]` (`IStringLocalizer` property).
- Elsewhere: inject `IStringLocalizer<TResource>`.
- Always localize user-facing strings and exception messages.
- Resource files: `*.Domain.Shared/Localization/{Resource}/{lang}.json`
  (layered) or `{{PROJECT_ROOT}}/Localization/{Resource}/{lang}.json`
  (single-layer).

## Anti-patterns (consult before generating code)

See **references/anti-patterns.md** for the full list with explanations.
The short version:

- No Minimal APIs, no MediatR, no `DbContext` in Application Services.
- No `DateTime.Now`, no manual `AddScoped` for app code.
- No business logic in controllers, no entities crossing the application boundary.
- No repositories for child entities — one repo per aggregate root.
- No hardcoded role checks — use permissions.
- No public setters on entities with business rules (private set + methods).
- No `Guid.NewGuid()` in entity constructors — use `GuidGenerator.Create()`
  from outside, pass `Guid id` into the constructor.

## When to delegate to other abp-* skills

| User intent | Skill |
|---|---|
| Add a new entity / DTO / AppService end-to-end | `abp-feature-dev` |
| Port a schema from Postgres/SQL/another system | `abp-feature-dev` |
| Configure MongoDB context, custom repositories, indexes | `abp-mongodb` |
| Make an entity tenant-aware, switch tenant context, configure tenant resolution | `abp-multitenancy` |
| Write integration tests for an AppService / DomainService | `abp-testing` |

This skill (`abp-core`) covers everything that crosses those areas: modules,
DI, base classes, audit/persistence choices, exceptions, async, time,
localization. When the user pulls in any of those concepts, surface them
here; when the user moves into a specialized concern, delegate.
