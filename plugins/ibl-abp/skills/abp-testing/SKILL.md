---
name: abp-testing
description: 'Integration testing patterns for ABP Framework projects: ApplicationTestBase, DomainTestBase, Shouldly, AAA, IDataSeedContributor test data, AddAlwaysAllowAuthorization, NSubstitute for external dependencies, CurrentUser.Change, CurrentTenant.Change, CRUD AppService tests, ApplyFilters coverage, lifecycle/state-machine tests, multi-tenancy isolation, bulk-operation tests, and MongoDB coverlet coverage hangs. Use to write or scaffold tests for ABP AppServices, DomainServices, repositories, permissions, per-user behavior, tenant behavior, lifecycle transitions, bulk operations, or backend coverage.'
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

with a standard CRUD **baseline** always included:
1. `Should_Get_List` — basic GetListAsync smoke test.
2. `Should_Get_{Entity}` — create or seed one row, then GetAsync by id.
3. `Should_Create_{Entity}` — happy-path create.
4. `Should_Update_{Entity}` — update at least one editable field.
5. `Should_Delete_{Entity}` — delete and verify the row no longer appears.
6. `Should_Throw_Validation_For_Invalid_Input` — `AbpValidationException` path.
7. `Should_Get_List_With_All_Filters` — exercise every supported list filter
   branch in `ApplyFilters` / `ApplyBaseFilters`.

Add focused tests for any entity-specific business rules:
- permission behavior when permission enforcement is part of the feature
- tenant isolation when the entity implements `IMultiTenant`
- lifecycle transitions when the entity has status/state behavior
- uniqueness or other invariant failures that should throw `BusinessException`

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

## Testing filters and coverage

`ApplyFilters` and `ApplyBaseFilters` often contain most of an AppService's
branching logic. Do not rely on a plain `GetListAsync(new Input())` smoke test
for meaningful coverage.

Add a dedicated `Should_Get_List_With_All_Filters` test when the list input has
typed filters:

1. Seed or create records that should match.
2. Seed or create nearby records that should not match.
3. Call `GetListAsync` with every supported query parameter populated in the
   same request: text, enum, bool, date ranges, numeric ranges, and foreign keys.
4. Assert that matching rows are present and non-matching rows are absent.

Use separate tests only when filters have independent edge cases that cannot be
represented clearly in one input.

## Coverage execution with MongoDB tests

ABP MongoDB tests that start embedded MongoDB or replica-set helpers such as
`MongoSandbox.Core` can keep background processes or sockets alive after tests
finish. VSTest data collectors such as `coverlet.collector` may then hang while
waiting for process exit.

Prefer `coverlet.msbuild` for these projects:

```powershell
dotnet test /p:CollectCoverage=true /p:CoverletOutputFormat=cobertura
```

Do not mix `coverlet.collector` and `coverlet.msbuild` in the same test run.
If coverage hangs after all tests pass, check the test `.csproj` first and move
collector-based coverage to MSBuild-based coverage before changing test logic.

Exclude generated or non-business infrastructure from coverage thresholds when
it would distort the signal: migration services, schema migrators, health
checks, entry points, generated controllers, branding providers, and mapping
glue. Keep AppServices, DomainServices, custom repositories, lifecycle rules,
permission behavior, and filters in scope.

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
- **Coverage run hangs after tests passed.** In MongoDB-backed test projects,
  suspect `coverlet.collector` interacting with embedded MongoDB background
  services before blaming the test body. Use `coverlet.msbuild`.
