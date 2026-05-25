# ABP Anti-Patterns

The ABP framework has opinionated conventions. Going against them usually means
re-inventing something ABP already does — and losing testability, multi-tenancy,
or auditing in the process.

## The big seven

| Don't | Use instead | Why |
|---|---|---|
| Minimal APIs | ABP Controllers / Auto API Controllers | Auto-discovery, conventional routing, integration with permission system, client proxy generation |
| MediatR | Application Services | Application Services *are* ABP's command/query layer. MediatR duplicates plumbing and bypasses ABP's interception (auth, UoW, validation). |
| `DbContext` injected in Application Services | `IRepository<T, TKey>` (or custom repository) | Repository abstracts the data provider — keeps the application layer DB-agnostic and testable |
| `AddScoped/AddTransient/AddSingleton<T>(...)` for app code | `ITransientDependency` / `IScopedDependency` / `ISingletonDependency` marker interfaces | Marker interfaces are conventional and survive refactors; manual registration must be remembered |
| `DateTime.Now` / `DateTime.UtcNow` | `Clock.Now` (property on base classes) or inject `IClock` | Respects ABP's timezone config; can be mocked in tests |
| Custom UnitOfWork helpers | `IUnitOfWorkManager` (auto-applied via `[UnitOfWork]` and ambient transactions) | UoW is already integrated with repositories, events, and middleware |
| Manual HTTP calls from UI | `abp generate-proxy` client proxies | Type-safe, auto-regenerated, includes correct serialization & error mapping |

## More subtle pitfalls

### Business logic in Controllers
Controllers should be thin: validate input, call an Application Service, return the result. Anything else belongs in an `ApplicationService` or `DomainService`.

### Anemic entities with public setters everywhere
For non-trivial business rules, prefer:
- private setters
- a primary constructor that validates invariants
- methods (`Order.Complete()`, `Book.SetPrice(...)`) for state transitions

Public setters are fine for **trivial** CRUD entities (especially in the single-layer template), but draw the line as soon as a rule appears.

### Repositories for child entities
**One repository per aggregate root.** A repository for `OrderLine` lets a caller mutate it without going through `Order`, bypassing invariants. In ABP, call `AddDefaultRepositories()` **without** `includeAllEntities: true`.

### Hardcoded role checks
```csharp
if (CurrentUser.IsInRole("admin")) { ... }   // ❌ couples logic to role names
[Authorize(MyPermissions.SomeAction)]        // ✅ permission-based, configurable per tenant/user
```

### Cross-module Application Service calls
Application Services should not depend on other Application Services in different modules. If you need to react to something across modules, publish a **distributed event** (ETO).

### Returning entities from Application Services
Always map to DTOs. Returning entities leaks domain state, breaks API contracts, and creates serialization headaches (lazy-loaded properties, navigation cycles, etc.).

### Forgetting `UpdateAsync` with MongoDB (or detached EF entities)
MongoDB has no change tracking. After mutating an entity, you must call `_repo.UpdateAsync(entity)` explicitly. The same applies to entities loaded outside a UoW or with `AsNoTracking()`.

### Generating Guids in entity constructors
```csharp
public Book(string name) : base(Guid.NewGuid())   // ❌ not testable
{
}
// Caller does:
new Book(GuidGenerator.Create(), name)            // ✅ id from outside
```

## Conventions checklist

Before submitting:

- [ ] Async methods end with `Async`
- [ ] No `.Result` / `.Wait()` anywhere
- [ ] No `DateTime.Now` — use `Clock`/`IClock`
- [ ] No new `IRepository<ChildEntity, ...>` injected
- [ ] No `DbContext` in Application layer
- [ ] No `IFormFile` / `Stream` in Application Service parameters (use `byte[]` from controllers)
- [ ] DTOs (not entities) crossing the application boundary
- [ ] Permissions checked via `[Authorize]` or `CheckPolicyAsync`, not role names
- [ ] `BusinessException` codes use a namespace prefix mapped to a localization resource
