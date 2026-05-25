---
name: abp-testing
description: 'Integration testing patterns for ABP Framework projects: ApplicationTestBase, DomainTestBase, Shouldly, AAA, IDataSeedContributor test data, AddAlwaysAllowAuthorization, NSubstitute for external dependencies, CurrentUser.Change, CurrentTenant.Change, lifecycle/state-machine tests, multi-tenancy isolation, and bulk-operation tests. Use to write or scaffold tests for ABP AppServices, DomainServices, repositories, permissions, per-user behavior, tenant behavior, lifecycle transitions, or bulk operations.'
---

# ABP Testing

ABP's testing story is opinionated: **prefer integration tests**, use the
real DI container with an in-memory database, and only mock the things that
truly cross process boundaries (email, HTTP, payment gateways). The result
is tests that catch wiring issues, validation flows, and permission policies
in the same run.

## The test project structure

A standard ABP solution has up to three test projects, each with its own
base class:

| Project | Base class | Use for |
|---|---|---|
| `*.Domain.Tests` | `*DomainTestBase` | Pure domain logic, entities, domain services |
| `*.Application.Tests` | `*ApplicationTestBase` | Application services (most common) |
| `*.EntityFrameworkCore.Tests` | `*EntityFrameworkCoreTestBase` | Custom repository implementations |

Single-layer templates collapse these into a single `*.Tests` project.

## The standard pattern

```csharp
public class BookAppService_Tests : {{PROJECT_NAME}}ApplicationTestBase
{
    private readonly IBookAppService _bookAppService;

    public BookAppService_Tests()
    {
        _bookAppService = GetRequiredService<IBookAppService>();
    }

    [Fact]
    public async Task Should_Create_Book_When_Input_Is_Valid()
    {
        // Arrange
        var input = new CreateBookDto { Name = "New Book", Price = 19.99m };

        // Act
        var result = await _bookAppService.CreateAsync(input);

        // Assert
        result.Id.ShouldNotBe(Guid.Empty);
        result.Name.ShouldBe("New Book");
    }
}
```

Conventions:
- **Naming**: `Should_<expected>_When_<condition>` (`Should_Throw_BusinessException_When_Name_Duplicates`). Reads as a sentence in test output.
- **AAA layout**: Arrange / Act / Assert, separated by blank lines. Skip the comments when the structure is already obvious.
- **One behavior per test.** If you find yourself asserting two unrelated things, split the test.
- **Use Shouldly** (`ShouldBe`, `ShouldNotBeNull`, `ShouldContain`, `Should.ThrowAsync<T>`). ABP ships with it; don't reach for FluentAssertions.

## Scaffolding a test for an AppService

```bash
# Derive name+namespace+features from the interface file (auto-detect mode)
python <skills-root>/abp-testing/scripts/scaffold_test.py \
    --entity-interface src/MyProject/Services/Books/IBookAppService.cs

# Or pass them directly
python <skills-root>/abp-testing/scripts/scaffold_test.py \
    --entity Book --plural Books

# Explicit include flags
python <skills-root>/abp-testing/scripts/scaffold_test.py \
    --entity Customer --plural Customers \
    --include lifecycle,multitenancy,bulk
```

The script auto-locates the test project (looks for `*ApplicationTestBase.cs`
under the solution root) and writes:

```
{TestProject}/Books/BookAppService_Tests.cs
```

with three **baseline** tests always included:
1. `Should_Get_List` — basic GetListAsync smoke test.
2. `Should_Create_{Entity}` — happy-path create.
3. `Should_Throw_Validation_For_Invalid_Input` — `AbpValidationException` path.

Plus optional blocks (added automatically when the AppService interface
exposes the relevant methods, or explicitly via `--include`):

| Block | Triggers when | Tests added |
|---|---|---|
| `lifecycle` | Interface has `ChangeStatusAsync` | Initial state, valid transition, invalid transition (BusinessException), idempotent same-state transition |
| `multitenancy` | Entity implements `IMultiTenant` | Cross-tenant isolation — records in tenant A invisible in tenant B |
| `bulk` | Interface has `DeleteByIdsAsync` or `DeleteAllAsync` | DeleteByIds, DeleteAll with filter |

You then fill in the `// TODO` markers and add tests for the entity-specific
business rules.

## Data seeding

For tests that need pre-existing data, write a one-shot seeder:

```csharp
public class {{PROJECT_NAME}}TestDataSeedContributor : IDataSeedContributor, ITransientDependency
{
    public static readonly Guid TestBookId = Guid.Parse("11111111-1111-1111-1111-111111111111");

    private readonly IRepository<Book, Guid> _bookRepo;
    public {{PROJECT_NAME}}TestDataSeedContributor(IRepository<Book, Guid> bookRepo)
        => _bookRepo = bookRepo;

    public async Task SeedAsync(DataSeedContext context)
    {
        if (await _bookRepo.FindAsync(TestBookId) != null) return;
        await _bookRepo.InsertAsync(
            new Book(TestBookId, "Seeded Book", 10m),
            autoSave: true);
    }
}
```

Tests reference the seeded IDs via the `public static readonly` fields. The
seeder runs once per test database — for ABP, that means once per fresh test
instance.

## Bypassing authorization in tests

By default permission checks run during tests, which is good for catching
authz regressions. If the bulk of your tests are about behavior — not
permissions — bypass them in the test module:

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    context.Services.AddAlwaysAllowAuthorization();
}
```

Then write dedicated permission tests separately, with the default policy
enforcement re-enabled.

## Testing with a specific user

```csharp
[Fact]
public async Task Should_Filter_By_Creator()
{
    using (CurrentUser.Change(TestData.UserId, TestData.UserName))
    {
        var result = await _bookAppService.GetMyBooksAsync();
        result.Items.ShouldAllBe(b => b.CreatorId == TestData.UserId);
    }
}
```

`CurrentUser.Change(...)` returns an `IDisposable`; the `using` scope
restores the previous identity automatically.

## Testing multi-tenancy

```csharp
[Fact]
public async Task Should_Isolate_By_Tenant()
{
    using (CurrentTenant.Change(TestData.TenantAId))
    {
        await _productAppService.CreateAsync(new CreateProductDto { Name = "A" });
    }

    using (CurrentTenant.Change(TestData.TenantBId))
    {
        var listForB = await _productAppService.GetListAsync(new GetProductListDto());
        listForB.Items.ShouldNotContain(p => p.Name == "A");
    }
}
```

Each `Change` block is a sealed tenant context. This is the only reliable
way to test that the multi-tenant filter is doing its job.

## Mocking external dependencies

For services that touch the outside world (email, SMS, payment, blob
storage), substitute them in the test module:

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    var emailSender = Substitute.For<IEmailSender>();
    emailSender.SendAsync(Arg.Any<string>(), Arg.Any<string>(), Arg.Any<string>())
               .Returns(Task.CompletedTask);
    context.Services.AddSingleton(emailSender);
}
```

Then in tests, assert on the substitute:

```csharp
await emailSender.Received(1).SendAsync("user@example.com", Arg.Any<string>(), Arg.Any<string>());
```

Mock only the boundary. Mocking internal services (repositories, domain
services) usually means the test is asserting on implementation, not
behavior.

## Common assertion patterns

```csharp
result.ShouldNotBeNull();
result.Items.Count.ShouldBe(3);
result.Items.ShouldContain(x => x.Id == expectedId);
result.Items.ShouldBeEmpty();

// Exception with type only
await Should.ThrowAsync<EntityNotFoundException>(() => _svc.GetAsync(missingId));

// Exception with code/message check
var ex = await Should.ThrowAsync<BusinessException>(() => _svc.DoX());
ex.Code.ShouldBe("{{ROOT_NAMESPACE}}:SomeError");
```

## Testing lifecycle / state-machine entities

When an entity has a `ChangeStatus(newStatus, IClock)` method (see the
`abp-feature-dev` lifecycle pattern), test five things:

1. **Initial state**: a freshly created entity has the documented starting
   state and `StatusChangedAt == null`.
2. **Valid transition**: the happy path for each allowed arrow in the state
   diagram. Assert state changed *and* `StatusChangedAt == Clock.Now`.
3. **Invalid transition**: pick a representative forbidden arrow. Assert
   `BusinessException` with the `InvalidStatusTransition` code.
4. **Idempotence**: `ChangeStatusAsync(currentStatus)` should be a no-op
   (no throw, no `StatusChangedAt` update).
5. **Timestamp**: substitute `IClock` (or use a known clock) and verify the
   timestamp matches.

For example:

```csharp
var ex = await Should.ThrowAsync<BusinessException>(async () =>
    await _customerAppService.ChangeStatusAsync(id,
        new ChangeCustomerStatusDto { NewStatus = CustomerStatus.Prospect }));
ex.Code.ShouldContain("InvalidStatusTransition");
```

## Testing bulk operations

`DeleteByIdsAsync` and `DeleteAllAsync(filter)` need three coverage points:

1. **Happy path** — delete N items by id and verify list is empty.
2. **Filter respected** — `DeleteAllAsync` with a filter must not touch
   non-matching rows.
3. **Soft-delete interaction** — if the entity is `FullAuditedAggregateRoot`,
   bulk delete sets `IsDeleted = true` and a fresh `GetListAsync` should not
   see them.

## Common pitfalls

- **Tests aren't independent.** The framework gives each test a fresh DB,
  but if you mutate static state (an in-memory cache, a static collection),
  that bleeds between tests. Keep test setup local.
- **Asserting on entity state instead of DTO state.** Tests should call the
  AppService and inspect the returned DTO — that's the contract. Touching the
  repository to verify state couples the test to internals.
- **Skipping the validation test.** `AbpValidationException` paths are easy
  to break by removing a `[Required]` attribute; one tiny test catches it.
- **Forgetting `Should.ThrowAsync`.** Plain `Should.Throw` on an async method
  returns a `Task` of exception and silently passes whether the call threw or
  not. Always use the async variant for async methods.
- **Lifecycle test that doesn't verify the timestamp.** "It didn't throw"
  is not enough — the test should also confirm `StatusChangedAt` was set,
  otherwise a regression where the entity skips the assignment would slip
  through.

## Code Coverage and Test Execution

When measuring and achieving code coverage goals on ABP backend projects, follow these practices to avoid execution hangs and ensure accurate metrics:

### 1. Resolving MongoDB Sandbox Hangs
If the test project uses an embedded replica set runner (like `MongoSandbox.Core`) which keeps background processes/sockets active in the app domain, VSTest data collectors (e.g. `coverlet.collector`) will hang indefinitely after test execution.
- **Fix**: Use `coverlet.msbuild` instead of `coverlet.collector` inside the `*.csproj` file. This instruments and collects coverage inline during MSBuild without hooking the runner's process exit.
- **Execution Command**:
  ```powershell
  dotnet test /p:CollectCoverage=true /p:CoverletOutputFormat=cobertura
  ```

### 2. Maximizing AppService Coverage
- **Standard CRUD Coverage**: Default ABP test scaffolding sometimes only checks `GetListAsync` and `CreateAsync`. Always write explicit tests for `GetAsync(id)`, `UpdateAsync(id, input)`, and `DeleteAsync(id)` to cover all CRUD endpoints.
- **Comprehensive ApplyFilters Testing**: The `ApplyFilters` (or `ApplyBaseFilters`) method usually accounts for a large portion of the AppService's logic. Write a dedicated `Should_Get_List_With_All_Filters` test case that passes *all* supported query parameters simultaneously (e.g. strings, enums, dates) to exercise all conditional filter branches in a single test run.
- **Boilerplate Exclusions**: Exclude database migration services, database schema migrators, health checks, entry points (`Program.cs`), branding providers, and data mappers (`ObjectMapping`) that do not contain business logic. This can be configured in the test `*.csproj` under `<PropertyGroup>`:
  ```xml
  <Exclude>[AssemblyName]RootNamespace.Data.*,[AssemblyName]RootNamespace.HealthChecks.*,[AssemblyName]RootNamespace.Program*,[AssemblyName]RootNamespace.Controllers.*,[AssemblyName]RootNamespace.ObjectMapping.*</Exclude>
  ```
