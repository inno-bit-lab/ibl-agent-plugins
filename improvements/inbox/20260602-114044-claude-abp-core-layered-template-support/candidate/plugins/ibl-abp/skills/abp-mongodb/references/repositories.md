# MongoDB repositories in ABP

> Official: <https://abp.io/docs/latest/framework/data/mongodb>

## When you need a custom repository

The generic `IRepository<TEntity, TKey>` covers all the standard cases:
`GetAsync`, `InsertAsync`, `UpdateAsync`, `DeleteAsync`, `GetListAsync`,
`GetQueryableAsync`, etc. Define a custom interface only when you have a
**named, reusable query** that the rest of the application should call by
name (e.g. `FindByOrderNumberAsync`).

The interface is the `repo_interface` artifact. It always lives in the
**Domain** layer: nolayers → the single project under `Data/{Plural}/`, ns
`{{ROOT_NAMESPACE}}.Data.{Plural}`; layered → the `*.Domain` project under
`{Plural}/`, ns `{{ROOT_NAMESPACE}}.{Plural}`. Run
`python <skills-root>/abp-core/scripts/abp_context.py --show-layout` for the
exact path; `resolve_artifact(ctx, "repo_interface", plural)` is the source of truth.

```csharp
// In the Domain layer (Data/{Plural}/ on nolayers, *.Domain/{Plural}/ on layered)
public interface IBookRepository : IRepository<Book, Guid>
{
    Task<Book?> FindByNameAsync(string name, CancellationToken ct = default);
    Task<List<Book>> GetListByAuthorAsync(Guid authorId, CancellationToken ct = default);
}
```

**Layered constraint — no input DTO in the interface signature.** The Domain
layer cannot reference `Application.Contracts`, so a list query here takes
**primitives** (`string? filterText` plus paging: `sorting`, `maxResultCount`,
`skipCount`), never `Get{Plural}Input`. Per-field filtering stays in the
AppService, which builds the predicate and calls the repository with the
plain values. In nolayers everything is one project so passing the input DTO
*compiles*, but keeping the primitive signature lets the same interface serve
both templates:

```csharp
Task<List<Book>> GetListAsync(
    string? filterText = null,
    string? sorting = null,
    int maxResultCount = int.MaxValue,
    int skipCount = 0,
    CancellationToken ct = default);
```

## Implementation

The implementation is the `repo_impl` artifact: nolayers → the single project
under `Data/{Plural}/`, ns `{{ROOT_NAMESPACE}}.Data.{Plural}`; layered → the
`*.MongoDB` project (`{{DATA_PROJECT}}`) under `MongoDb/{Plural}/`, ns
`{{ROOT_NAMESPACE}}.MongoDB`. The class name convention is `Mongo{Entity}Repository`
on layered (e.g. `MongoBookRepository`). The base class is identical on both —
`MongoDbRepository<{{ROOT_NAMESPACE}}MongoDbContext, {Entity}, Guid>` — only the
context's namespace differs (`.Data` vs `.MongoDB`), so add the matching `using`.

```csharp
public class BookRepository
    : MongoDbRepository<{{ROOT_NAMESPACE}}MongoDbContext, Book, Guid>,
      IBookRepository
{
    public BookRepository(IMongoDbContextProvider<{{ROOT_NAMESPACE}}MongoDbContext> provider)
        : base(provider) { }

    public async Task<Book?> FindByNameAsync(string name, CancellationToken ct = default)
    {
        return await (await GetQueryableAsync())
            .FirstOrDefaultAsync(b => b.Name == name, GetCancellationToken(ct));
    }

    public async Task<List<Book>> GetListByAuthorAsync(Guid authorId, CancellationToken ct = default)
    {
        return await (await GetQueryableAsync())
            .Where(b => b.AuthorId == authorId)
            .ToListAsync(GetCancellationToken(ct));
    }
}
```

Notes:
- Always go through `GetQueryableAsync()` — direct collection access bypasses
  data filters (soft-delete, multi-tenancy).
- Wrap caller-provided `CancellationToken` with `GetCancellationToken(ct)`
  so ABP can layer in its own cancellation sources.
- Don't use `includeDetails: true` semantics here — MongoDB documents embed
  related data inline, there's nothing extra to "include." Keep the
  parameter in the interface only if you're sharing it with an EFCore
  implementation.

## Direct collection access

For bulk operations or operators the LINQ provider doesn't translate well:

```csharp
public async Task PublishAllByAuthorAsync(Guid authorId)
{
    var collection = await GetCollectionAsync();
    var filter = Builders<Book>.Filter.Eq(b => b.AuthorId, authorId);
    var update = Builders<Book>.Update.Set(b => b.IsPublished, true);
    await collection.UpdateManyAsync(filter, update);
}
```

**Be careful**: direct collection writes skip ABP's auditing, soft-delete,
multi-tenant, and outbox interception. Use only when the LINQ path won't do.

## No change tracking — call UpdateAsync explicitly

Unlike EF Core, MongoDB repositories don't track entity changes. After
mutating an entity, **you must call** `UpdateAsync`:

```csharp
public async Task UpdatePriceAsync(Guid bookId, decimal newPrice)
{
    var book = await _bookRepo.GetAsync(bookId);
    book.SetPrice(newPrice);
    await _bookRepo.UpdateAsync(book);   // ← required
}
```

If you forget this, the in-memory entity is updated but nothing reaches the
database. This is the single most common MongoDB+ABP bug.

## Registering repositories

In your `*MongoDbModule.cs` (the `{{DATA_PROJECT}}` project on layered, the
single project on nolayers — it's wherever `AddMongoDbContext` already lives):

```csharp
context.Services.AddMongoDbContext<{{ROOT_NAMESPACE}}MongoDbContext>(options =>
{
    options.AddDefaultRepositories();
    // ⚠ Don't pass `includeAllEntities: true` — it would generate
    // generic repositories for child entities and let callers bypass
    // your aggregate roots.

    options.AddRepository<Book, BookRepository>();   // custom impl
});
```

`register_entity_in_context.py --register-repository` inserts this line for you
and finds the module automatically; the repo `using` it adds is template-correct
(`{{ROOT_NAMESPACE}}.Data.{Plural}` on nolayers, `{{ROOT_NAMESPACE}}.MongoDB` on layered).

## Indexes

ABP doesn't have a declarative index API for MongoDB. Two patterns:

**Lazy creation on first query** (simplest, fine for app-level indexes):

```csharp
public override async Task<IQueryable<Book>> GetQueryableAsync()
{
    var col = await GetCollectionAsync();
    await col.Indexes.CreateOneAsync(new CreateIndexModel<Book>(
        Builders<Book>.IndexKeys.Ascending(b => b.Name)));
    return await base.GetQueryableAsync();
}
```

**Startup-time creation** (preferred for production — explicit, no per-query
overhead): create indexes in a hosted service or data seeder during app
initialization.

## Embedded vs referenced

```csharp
// Embedded — child documents stored in the parent's BSON
public class Order : AggregateRoot<Guid>
{
    public List<OrderLine> Lines { get; private set; } = new();
}

// Referenced — store the foreign id only; load via a separate query
public class Order : AggregateRoot<Guid>
{
    public Guid CustomerId { get; private set; }   // no nav property
}
```

Embed when:
- The child is always loaded with the parent.
- The child has no independent lifecycle.
- The child doesn't grow unboundedly (a single document is capped at 16 MB).

Reference when:
- The data is updated independently (different writers, different rates).
- The child is queried across many parents.
- You expect the count to grow without bound.

## Data filters still apply

ABP filters work over MongoDB too:
- `ISoftDelete` — `IsDeleted=true` documents are filtered out by default.
- `IMultiTenant` — queries are filtered by `CurrentTenant.Id` automatically.

To bypass temporarily (e.g. a host-side admin tool):

```csharp
using (DataFilter.Disable<IMultiTenant>())
{
    var all = await _bookRepo.GetListAsync();
}
```
