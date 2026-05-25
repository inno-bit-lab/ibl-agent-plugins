# Authorization in ABP

> Official: <https://abp.io/docs/latest/framework/fundamentals/authorization>

ABP authorization is **permission-based**, not role-based. Roles are just
bundles of permissions; business code checks permissions directly.

## Defining permissions

A permission has a string name; group/parent structure is for the
administration UI. Define them in a static class (one per module/feature
area):

```csharp
public static class {{ROOT_NAMESPACE}}Permissions
{
    public const string GroupName = "{{ROOT_NAMESPACE}}";

    public static class Books
    {
        public const string Default = GroupName + ".Books";
        public const string Create  = Default + ".Create";
        public const string Edit    = Default + ".Edit";
        public const string Delete  = Default + ".Delete";
    }
}
```

Register them in a provider so the admin UI can manage them:

```csharp
public class {{ROOT_NAMESPACE}}PermissionDefinitionProvider : PermissionDefinitionProvider
{
    public override void Define(IPermissionDefinitionContext context)
    {
        var group = context.AddGroup({{ROOT_NAMESPACE}}Permissions.GroupName,
            L("Permission:{{ROOT_NAMESPACE}}"));

        var books = group.AddPermission({{ROOT_NAMESPACE}}Permissions.Books.Default,
            L("Permission:Books"));
        books.AddChild({{ROOT_NAMESPACE}}Permissions.Books.Create, L("Permission:Books.Create"));
        books.AddChild({{ROOT_NAMESPACE}}Permissions.Books.Edit,   L("Permission:Books.Edit"));
        books.AddChild({{ROOT_NAMESPACE}}Permissions.Books.Delete, L("Permission:Books.Delete"));
    }

    private static LocalizableString L(string name)
        => LocalizableString.Create<{{PROJECT_NAME}}Resource>(name);
}
```

## Checking permissions

**Declarative** (preferred — visible at the method signature):

```csharp
[Authorize({{ROOT_NAMESPACE}}Permissions.Books.Create)]
public virtual Task<BookDto> CreateAsync(CreateBookDto input) { ... }
```

**Programmatic** (when the decision depends on data):

```csharp
public async Task UpdateAsync(Guid id, UpdateBookDto input)
{
    await CheckPolicyAsync({{ROOT_NAMESPACE}}Permissions.Books.Edit);

    // Or non-throwing check:
    if (await IsGrantedAsync({{ROOT_NAMESPACE}}Permissions.Books.Delete))
    {
        // allow soft-delete
    }
}
```

**Anonymous endpoints** (login, public lookups):

```csharp
[AllowAnonymous]
public Task<BookDto> GetPublicAsync(Guid id) { ... }
```

## Ownership checks

Permission alone says *"this user can edit some books"*, not *"this user can
edit *this* book."* For per-record authorization, layer on an explicit check:

```csharp
public async Task UpdateMyBookAsync(Guid bookId, UpdateBookDto input)
{
    var book = await _bookRepo.GetAsync(bookId);
    if (book.CreatorId != CurrentUser.Id)
        throw new AbpAuthorizationException();
    // ...
}
```

For data-filtering across many records, prefer:
- a repository query parameter (`GetMyBooksAsync(userId)`), or
- a custom `IDataFilter<T>` if the rule applies broadly.

## Multi-tenancy interaction

A permission can be restricted to a tenancy side:

```csharp
group.AddPermission(
    {{ROOT_NAMESPACE}}Permissions.Books.Default,
    L("Permission:Books"),
    multiTenancySide: MultiTenancySides.Tenant); // hides from Host admin UI
```

Options: `MultiTenancySides.Host`, `Tenant`, or `Both` (default).

## Feature dependencies

If a permission only matters when a paid feature is enabled:

```csharp
booksPermission.RequireFeatures("{{ROOT_NAMESPACE}}.PremiumFeature");
```

## Programmatic permission management

```csharp
public class GrantService : ITransientDependency
{
    private readonly IPermissionManager _permissionManager;
    public GrantService(IPermissionManager pm) => _permissionManager = pm;

    public Task GrantToUserAsync(Guid userId, string permission)
        => _permissionManager.SetForUserAsync(userId, permission, isGranted: true);

    public Task GrantToRoleAsync(string roleName, string permission)
        => _permissionManager.SetForRoleAsync(roleName, permission, isGranted: true);
}
```

## Security guardrails

- Never trust client input for user identity — use `CurrentUser`.
- Don't hardcode role checks (`CurrentUser.IsInRole("admin")`). Promote
  whatever you wanted to gate into a permission.
- Don't expose sensitive fields in DTOs (password hashes, internal flags).
- Validate ownership on every per-record operation.
- Filter list queries by `CurrentUser.Id` / `CurrentTenant.Id` server-side —
  never rely on the UI to do it.
