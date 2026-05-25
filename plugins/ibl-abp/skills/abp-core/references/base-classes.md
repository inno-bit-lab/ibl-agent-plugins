# ABP Base Classes — Quick Reference

When working in a class that inherits from one of these, **check first** whether
the service you're about to inject is already available as a property. Injecting
something the base class already gives you wastes constructor noise.

## Inheritance tree (most-used)

| Base class | Inherits from | Typical use |
|---|---|---|
| `Entity<TKey>` | — | Basic entity with ID |
| `AggregateRoot<TKey>` | `Entity<TKey>` | DDD aggregate root (publishes events) |
| `AuditedAggregateRoot<TKey>` | `AggregateRoot<TKey>` | Adds CreationTime, CreatorId, LastModifier* |
| `FullAuditedAggregateRoot<TKey>` | `AuditedAggregateRoot<TKey>` | Adds Deleter* + IsDeleted (soft-delete) |
| `DomainService` | — | Cross-aggregate business logic (`*Manager`) |
| `ApplicationService` | — | Use-case orchestration |
| `AbpController` | `ControllerBase` | REST API controller |
| `AbpPageModel` | `PageModel` | Razor Pages |

## Properties provided by base classes

| Property | Available in | Description |
|---|---|---|
| `GuidGenerator` | All | `IGuidGenerator` — generate GUIDs |
| `Clock` | All | `IClock` — current time (use instead of `DateTime.Now/UtcNow`) |
| `CurrentUser` | All | `ICurrentUser` — authenticated user (Id, UserName, Email, Roles, TenantId, IsAuthenticated) |
| `CurrentTenant` | All | `ICurrentTenant` — multi-tenancy context (Id, Name, IsAvailable, Change(...)) |
| `DataFilter` | All | `IDataFilter` — toggle soft-delete / multi-tenant filters |
| `LoggerFactory` | All | `ILoggerFactory` |
| `Logger` | All | Auto-created `ILogger<TSelf>` |
| `LazyServiceProvider` | All | Resolve services lazily |
| `L` (`IStringLocalizer`) | `ApplicationService`, `AbpController`, `AbpPageModel` | Localization — `L["Key"]` |
| `AuthorizationService` | `ApplicationService`, `AbpController` | `IAuthorizationService` — permission checks |
| `FeatureChecker` | `ApplicationService`, `AbpController` | `IFeatureChecker` — feature flags per tenant |
| `UnitOfWorkManager` | `ApplicationService`, `DomainService` | `IUnitOfWorkManager` |

## Useful methods (from base classes)

- `CheckPolicyAsync(permission)` — checks permission, throws `AbpAuthorizationException` if denied.
- `IsGrantedAsync(permission)` — returns bool, never throws.
- `CurrentTenant.Change(tenantId)` — `using`-scoped tenant switch.
- `DataFilter.Disable<IMultiTenant>()` — `using`-scoped filter bypass.

## Marker interfaces (DI auto-registration)

| Interface | Lifetime |
|---|---|
| `ITransientDependency` | Transient |
| `IScopedDependency` | Scoped |
| `ISingletonDependency` | Singleton |

`ApplicationService`, `DomainService`, `AbpController`, and `Profile` (AutoMapper)
are already auto-registered — don't add a marker interface to them.

## When to inject vs use property

```csharp
// Inside an ApplicationService — DON'T inject things you already have:
public class BookAppService : ApplicationService
{
    public BookAppService(IClock clock, ICurrentUser user) // ❌ both already on base
    {
    }
}

// Correct:
public class BookAppService : ApplicationService
{
    public async Task DoSomethingAsync()
    {
        var now = Clock.Now;             // ✅ from base
        var userId = CurrentUser.Id;     // ✅ from base
        var localized = L["BookName"];   // ✅ from base
    }
}

// In a plain service that doesn't inherit from a base class — DO inject:
public class MyHelper : ITransientDependency
{
    private readonly IClock _clock;
    public MyHelper(IClock clock) => _clock = clock;
}
```
