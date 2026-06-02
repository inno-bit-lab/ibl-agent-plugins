---
name: abp-mongodb
description: 'ABP Framework + MongoDB integration: configure AbpMongoDbContext, register entity collections, add custom MongoDbRepository implementations, typed filters, indexes, embedded/reference documents, enum string setup, and explicit UpdateAsync behavior because MongoDB has no change tracking. Use when adding a Mongo-backed ABP entity or working with MongoDbContext, IMongoCollection, MongoDbRepository, IMongoDbContextProvider, AddMongoDbContext, GetQueryableAsync, GetCollectionAsync, indexes, compound indexes, tenant-aware uniqueness, or collection registration.'
---

# ABP + MongoDB

This skill covers the MongoDB-specific layer of an ABP project: the
`AbpMongoDbContext`, repository patterns (generic + custom), indexes
(single, compound, tenant-aware unique), and the differences from EF Core
that bite teams new to the stack.

For framework-wide conventions (DI, base classes, async, etc.) see
`abp-core`. For the entity/AppService/DTO scaffold see `abp-feature-dev`.
For modular ownership decisions see `abp-module-architecture`.

## Context selection in modular solutions

If the solution has `modules/`, choose the Mongo context owned by the module
that owns the entity. Do not register a CRM entity in the host context just
because the host can see it.

Rules:

- Feature entity collection properties belong in the feature module context.
- Shared abstractions are registered only when they are concrete persisted
  aggregate roots; base classes/value objects usually do not need collections.
- Index seed contributors live beside the module context and use that module's
  `IMongoDbContextProvider<TModuleMongoDbContext>`.
- Keep collection names stable while moving modules unless there is an explicit
  data migration.
- If the module uses a named connection string, add the matching key or let it
  fall back deliberately to `Default`; do not leave the name accidental.

## The two mental shifts from EF Core

1. **No change tracking.** Repositories don't watch your entity for changes;
   you must call `await _repo.UpdateAsync(entity)` after mutating it.
2. **No migrations.** MongoDB is schemaless. Structural changes happen at
   runtime; data migrations (renames, splits, computed fields) are explicit
   scripts you write yourself.

## Where the context and repositories live (nolayers vs layered)

ABP lays the same Mongo code out differently per template. Locations and
namespaces are resolved centrally by `resolve_artifact(ctx, kind, plural)` in
`abp-core/scripts/abp_context.py` — run `python <skills-root>/abp-core/scripts/abp_context.py --show-layout`
in the solution to print the exact dir + namespace for every artifact. The
table below is the summary for the pieces this skill touches:

| Artifact | nolayers (single project / IBL360) | layered (DDD / IBLTermocasa) |
|---|---|---|
| `*MongoDbContext` | `{{PROJECT_ROOT}}/Data/`, ns `{{ROOT_NAMESPACE}}.Data` | `{{DATA_PROJECT}}/MongoDb/`, ns `{{ROOT_NAMESPACE}}.MongoDB` |
| Custom repo **interface** | `{{PROJECT_ROOT}}/Data/{Plural}/`, ns `{{ROOT_NAMESPACE}}.Data.{Plural}` | `{{DOMAIN_PROJECT}}/{Plural}/`, ns `{{ROOT_NAMESPACE}}.{Plural}` |
| Custom repo **implementation** | `{{PROJECT_ROOT}}/Data/{Plural}/`, ns `{{ROOT_NAMESPACE}}.Data.{Plural}` | `{{DATA_PROJECT}}/MongoDb/{Plural}/`, ns `{{ROOT_NAMESPACE}}.MongoDB` |
| Index seed contributor | `{{PROJECT_ROOT}}/Data/` | `{{DOMAIN_PROJECT}}/{Plural}/` |

`{{DATA_PROJECT}}` is the `*.MongoDB` project in layered and collapses to
`{{PROJECT_ROOT}}` in nolayers, so the same placeholder works on both. The
examples below use the nolayers namespaces (`{{ROOT_NAMESPACE}}MongoDbContext`,
`{{ROOT_NAMESPACE}}.Data.*`); on layered the context namespace is
`{{ROOT_NAMESPACE}}.MongoDB` — real example
`src/IBLTermocasa.MongoDB/MongoDb/IBLTermocasaMongoDbContext.cs` with
`namespace IBLTermocasa.MongoDB;`.

## Configuring the DbContext

```csharp
[ConnectionStringName("Default")]
public class {{ROOT_NAMESPACE}}MongoDbContext : AbpMongoDbContext
{
    public IMongoCollection<Book>   Books   => Collection<Book>();
    public IMongoCollection<Author> Authors => Collection<Author>();

    protected override void CreateModel(IMongoModelBuilder modelBuilder)
    {
        base.CreateModel(modelBuilder);

        modelBuilder.Entity<Book>(b =>
        {
            b.CollectionName = "Books";
        });

        modelBuilder.Entity<Author>(b =>
        {
            b.CollectionName = "Authors";
        });
    }
}
```

The collection name in `CreateModel` is what actually lands in MongoDB — by
default ABP would use the entity class name, but specifying it explicitly
shields you from accidental renames.

## Adding an entity to an existing context

When you add a new entity, three things must change in `*MongoDbContext.cs`:

1. A `using` for the entity's namespace.
2. A new `IMongoCollection<TEntity> {Plural} => Collection<TEntity>();` property.
3. A new `modelBuilder.Entity<TEntity>(b => { b.CollectionName = "..."; });`
   block inside `CreateModel`.

If the entity has a **custom repository** (see further down), one more thing
must change — in `*Module.cs`:

4. `options.AddRepository<TEntity, MongoTEntityRepository>();` inside the
   `AddMongoDbContext<>()` call.

The bundled script does all of this idempotently, and auto-detects the
template so it finds the right context file and computes the right
namespace on both layouts:

```bash
# Interactive — prompts for missing values
python <skills-root>/abp-mongodb/scripts/register_entity_in_context.py

# Scripted — namespace flags are optional; omit them to use the
# template-correct default from resolve_artifact (Root.Entities.Customers
# on nolayers, Root.Customers on layered) and let the script find the context.
python <skills-root>/abp-mongodb/scripts/register_entity_in_context.py \
    --entity Customer --plural Customers

# With custom repository registration — repo namespace also defaults correctly
# (Root.Data.Customers on nolayers, Root.MongoDB on layered), so you can drop it too.
python <skills-root>/abp-mongodb/scripts/register_entity_in_context.py \
    --entity Customer --plural Customers \
    --repository-name MongoCustomerRepository \
    --register-repository
```

Pass `--entity-namespace` / `--repository-namespace` only to override the
resolver (e.g. a non-standard folder). On layered, the entity namespace
equals the context's own namespace for some aggregates, and the script
skips a redundant `using` in that case.

The script:
- Reports `[skip]` for any change already in place — safe to re-run.
- Synthesizes `CreateModel` if missing.
- Locates the `*Module.cs` automatically when `--register-repository` is
  passed, and inserts the `AddRepository<>` line inside the
  `AddMongoDbContext<>` call.

## Connection string

```json
{
  "ConnectionStrings": {
    "Default": "mongodb://localhost:27017/{{PROJECT_NAME}}Db"
  }
}
```

The `ConnectionStringName("Default")` attribute on the DbContext class points
at this key. To shard contexts across databases (rare), give each one its own
`[ConnectionStringName("…")]` and a matching entry in `appsettings.json`.

## Module wiring

```csharp
[DependsOn(typeof(AbpMongoDbModule))]
public class {{ROOT_NAMESPACE}}MongoDbModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        context.Services.AddMongoDbContext<{{ROOT_NAMESPACE}}MongoDbContext>(options =>
        {
            options.AddDefaultRepositories();
            // Don't pass `includeAllEntities: true` — see references/repositories.md
            options.AddRepository<Customer, MongoCustomerRepository>();  // custom impl
        });
    }
}
```

## When to add a custom repository

Default to the **generic** `IRepository<T, TKey>` for plain CRUD. Add a
**custom** repository when:

- The feature has **more than ~5 filters** and the LINQ chain repeats across
  list / export / delete-all endpoints. A custom repository holds an
  `ApplyFilter(IQueryable<T>, GetXInput)` method that all three callers use.
- The feature needs **named domain queries** (`FindByTaxIdAsync`,
  `GetActiveByOwnerAsync`).
- The feature needs an operator MongoDB LINQ doesn't translate well — drop
  to `GetCollectionAsync()` and `Builders<T>` inside the repository.

The `abp-feature-dev` scaffolder generates a custom repository when the
filter spec has >3 entries, or when you pass `--custom-repository yes`. See
`references/repositories.md` for the full shape.

## Repository patterns (short version)

- Use `GetQueryableAsync()` for LINQ; `GetCollectionAsync()` only for
  driver-level bulk ops or operators LINQ can't translate.
- Always cast back to `IMongoQueryable<T>` after a `Where(...)` chain to keep
  the Mongo provider — `MongoDB.Driver.Linq.IMongoQueryable<T>`.
- After mutating an entity: **`await _repo.UpdateAsync(entity)`** every time.
- ABP data filters (`ISoftDelete`, `IMultiTenant`) work through the
  repository — bypass via `DataFilter.Disable<...>()`.

See **references/repositories.md** for the full pattern: custom interfaces,
direct collection access, indexes, embedded vs referenced documents.

## Indexes

> **The trap to avoid:** `IMongoEntityModelBuilder<T>` (the `b` you receive inside
> `modelBuilder.Entity<T>(b => { ... })`) does **NOT** expose `ConfigureCollection`,
> `Indexes`, or any way to declare indexes — that's a recurring hallucination.
> The builder only configures the collection name (`b.CollectionName = "..."`) and
> a few naming hints. Indexes must be created against the live `IMongoCollection<T>`
> through one of the patterns below.

Three patterns, in order of preference for production:

### Pattern 1 — `IDataSeedContributor` (recommended)

Runs once at app startup via `migrate-database` / data-seed pipeline. Idempotent
(`CreateOneAsync` is a no-op when the same index already exists). Centralizes
all indexes for one entity in one file.

The seed contributor is `data_seed` in the resolver: nolayers → `{{PROJECT_ROOT}}/Data/`;
layered → the Domain project, `{{DOMAIN_PROJECT}}/{Plural}/`. Either way it injects the
context via `IMongoDbContextProvider<{{ROOT_NAMESPACE}}MongoDbContext>` (the context type
is the same; only its namespace differs by template — `.Data` vs `.MongoDB`).

```csharp
using System.Threading.Tasks;
using MongoDB.Bson;
using MongoDB.Driver;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.MongoDB;
using Volo.Abp.Uow;

public class CustomerIndexInitializer : IDataSeedContributor, ITransientDependency
{
    private readonly IMongoDbContextProvider<{{ROOT_NAMESPACE}}MongoDbContext> _dbContextProvider;
    private readonly IUnitOfWorkManager _uowManager;

    public CustomerIndexInitializer(
        IMongoDbContextProvider<{{ROOT_NAMESPACE}}MongoDbContext> dbContextProvider,
        IUnitOfWorkManager uowManager)
    {
        _dbContextProvider = dbContextProvider;
        _uowManager = uowManager;
    }

    public async Task SeedAsync(DataSeedContext context)
    {
        using var uow = _uowManager.Begin(requiresNew: true);

        var dbContext = await _dbContextProvider.GetDbContextAsync();
        var collection = dbContext.Customers;
        var keys = Builders<Customer>.IndexKeys;

        // UNIQUE WHERE tax_id IS NOT NULL — scoped per tenant
        await collection.Indexes.CreateOneAsync(new CreateIndexModel<Customer>(
            keys.Ascending(c => c.TenantId).Ascending(c => c.TaxId),
            new CreateIndexOptions<Customer>
            {
                Name = "ux_customers_tenant_taxid",
                Unique = true,
                PartialFilterExpression = new BsonDocument("TaxId", new BsonDocument("$type", "string"))
            }));

        await collection.Indexes.CreateOneAsync(new CreateIndexModel<Customer>(
            keys.Ascending(c => c.Status),
            new CreateIndexOptions { Name = "ix_customers_status" }));

        await uow.CompleteAsync();
    }
}
```

Why this beats alternatives:
- Idempotent — safe across redeploys, no "already exists" handling needed.
- Runs on `migrate-database` so indexes appear before the first user request,
  not on the first query.
- One file per entity → easy to audit what's indexed.

### Pattern 2 — Lazy creation on first query

Simplest. Acceptable for small projects or app-level indexes you're prototyping.
Pays a tiny per-process overhead and ties index DDL to repository read code:

```csharp
public override async Task<IQueryable<Book>> GetQueryableAsync()
{
    var col = await GetCollectionAsync();
    await col.Indexes.CreateOneAsync(new CreateIndexModel<Book>(
        Builders<Book>.IndexKeys.Ascending(b => b.Name)));
    return await base.GetQueryableAsync();
}
```

### Pattern 3 — Hosted service

Use only when you can't get a `IDataSeedContributor` to run (no migrator
pipeline, or you need indexes to be checked on *every* host startup
regardless of whether seeds ran).

### Tenant-aware unique indexes (compound)

When porting a Postgres `UNIQUE` constraint to a multi-tenant Mongo collection,
**a single-field unique index is wrong** — it would prevent two tenants from
having the same `TaxId`. Use a compound `(TenantId, Field)` unique index:

```csharp
await collection.Indexes.CreateOneAsync(new CreateIndexModel<Customer>(
    Builders<Customer>.IndexKeys
        .Ascending(c => c.TenantId)
        .Ascending(c => c.TaxId),
    new CreateIndexOptions<Customer>
    {
        Unique = true,
        // MongoDB equivalent of WHERE TaxId IS NOT NULL.
        // Filter.Ne(c => c.TaxId, null) sometimes won't translate to a valid
        // partialFilterExpression; the BsonDocument form below is what the
        // driver accepts unambiguously across versions.
        PartialFilterExpression = new BsonDocument("TaxId", new BsonDocument("$type", "string")),
        Name = "ux_customers_tenant_taxid"
    }));
```

Notes:
- `PartialFilterExpression` is the MongoDB equivalent of `WHERE field IS NOT NULL`
  in Postgres — required for unique-when-not-null semantics.
- Always **name** the index explicitly. The auto-generated name from
  multi-field indexes is hard to read in logs.
- For Pattern 1 (the recommended one), wrap the work in a `using var uow =
  _uowManager.Begin(requiresNew: true)` block so the seed contributor doesn't
  fight with the ambient UoW that `migrate-database` opens.

## Storing enums as strings (not integers)

The MongoDB C# driver serializes enums as **integers by default**. Two big
downsides for app-level enums (`Status`, `Segment`, `Type`):

- Documents become unreadable when inspecting the DB directly (you see
  `status: 1` instead of `status: "Active"`).
- Reordering enum members silently corrupts existing data (the old `1` now
  means something else).

Three ways to fix it, listed best-first:

### Convention (truly global — recommended)

Register `EnumRepresentationConvention` once and **every** enum on every
entity, present and future, is stored as a string. No per-property
attributes, no per-type registrations. Put this in `*Module.PreConfigureServices`
(must run before the first `BsonClassMap` is built):

```csharp
using MongoDB.Bson;
using MongoDB.Bson.Serialization.Conventions;

public override void PreConfigureServices(ServiceConfigurationContext context)
{
    ConventionRegistry.Register(
        "{{ROOT_NAMESPACE}}EnumAsString",
        new ConventionPack { new EnumRepresentationConvention(BsonType.String) },
        _ => true);   // applies to all types
}
```

The third argument is a `Func<Type, bool>` — return `true` to opt every
type in, or scope it to a namespace if you want a more surgical roll-out:

```csharp
ConventionRegistry.Register(
    "{{ROOT_NAMESPACE}}EnumAsString",
    new ConventionPack { new EnumRepresentationConvention(BsonType.String) },
    t => t.FullName?.StartsWith("{{ROOT_NAMESPACE}}.Entities.") == true);
```

Conventions are applied lazily, when each `BsonClassMap` is built. As long
as registration happens in `PreConfigureServices` it's in place before any
collection is opened.

### Per-property attribute — surgical opt-in

Use when you have a *mixed* model (some enums string, others int, e.g.
internal numeric flags) and you don't want a convention to flip them all:

```csharp
using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

public class Customer : AuditedAggregateRoot<Guid>, IMultiTenant
{
    [BsonRepresentation(BsonType.String)]
    public CustomerSegment Segment { get; set; }
}
```

### Per-type serializer — rarely needed

`BsonSerializer.TryRegisterSerializer(typeof(MyEnum), new EnumSerializer<MyEnum>(BsonType.String))`
works but you have to call it once per enum type — same maintenance burden
as the attribute, without the locality benefit. Prefer the convention or
the attribute.

### REST API + OpenAPI representation

The Bson representation controls **storage**, not the JSON API surface.
ASP.NET still serializes enums as integers by default — and Swashbuckle
(the OpenAPI generator ABP uses) reads from MVC's `JsonOptions`, so an
inconsistent setup gives you `"status": "Active"` on the wire but
`type: integer, enum: [0,1,2]` in `/swagger/v1/swagger.json`. Clients
generated from that spec (TypeScript, C#, OpenAPI Generator) will then
expect numbers and break at runtime.

To make storage + REST + OpenAPI agree, pair the convention with
`JsonStringEnumConverter` on **both** serializers:

```csharp
// REST API surface (and OpenAPI: Swashbuckle picks this up automatically)
context.Services.Configure<Microsoft.AspNetCore.Mvc.JsonOptions>(o =>
    o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter()));

// ABP-internal JSON: proxies, dynamic HTTP clients, integration events.
// Recommended for the same reason — without this, outbound JSON can still
// emit integers even though the REST surface emits strings.
context.Services.Configure<Volo.Abp.Json.SystemTextJson.AbpSystemTextJsonSerializerOptions>(o =>
    o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter()));
```

### Verifying the setup (and fixing it)

It's easy to forget one of the three layers (convention, MVC converter,
ABP converter) — and the failure mode is silent until a generated client
breaks. Use the bundled script to verify all three, and optionally patch
the `*Module.cs` in place:

```bash
# Report missing pieces, exit non-zero if any FAIL
python <skills-root>/abp-mongodb/scripts/verify_enum_string_setup.py

# Insert the missing snippets into *Module.cs and re-check
python <skills-root>/abp-mongodb/scripts/verify_enum_string_setup.py --fix
```

**After applying the fix, re-run `migrate-database`** so any seed-time
data that embedded enum values is rewritten with the new representation.
For pre-existing application data, the driver still **reads** old-format
documents (integers); subsequent writes use the new format. For a clean
cutover run a one-shot `updateMany` per collection mapping integers to
names — typical pattern:

```javascript
db.Customers.find({ Status: { $type: "int" } }).forEach(doc => {
  db.Customers.updateOne(
    { _id: doc._id },
    { $set: { Status: ["Prospect", "Active", "Churned"][doc.Status] } }
  );
});
```

Make this a verification step on every feature that introduces an enum —
the skill `abp-feature-dev` calls this script automatically as part of
`verify_feature.py`, so a freshly scaffolded entity with enums will fail
verification until the convention + converters are in place.

### Migration note

Flipping representation does NOT back-fill existing documents. Pre-existing
records keep their old encoding until rewritten. For a clean cutover, run
a one-shot `updateMany` mapping the integer values to their string names,
or wait it out if the data churn is fast.

### Localization

Localization keys must match the chosen representation. With string
storage, prefer name-based keys (`Enum:CustomerStatus.Prospect`) over
index-based (`Enum:CustomerStatus.0`). Index-based keys are brittle:
adding a member in the middle of the enum silently breaks all UI labels.

## Common pitfalls

| Symptom | Likely cause |
|---|---|
| Saved entity not reflected in next read | Forgot `UpdateAsync` after mutation |
| `Where(...)` query returns nothing despite data in DB | Multi-tenant filter (different `TenantId`) or soft-delete filter |
| `InvalidOperationException` calling LINQ method | Operator not supported by Mongo LINQ — drop down to `GetCollectionAsync()` and `Builders<T>` |
| Repository injected but custom methods don't exist | You defined a custom interface but didn't register it — add `AddRepository<T, TImpl>()` (or pass `--register-repository` to the script) |
| `CollectionName` mismatch | Some entities default to class name, some are configured — always set explicitly in `CreateModel` |
| Compile error after `Where(...)` in a custom repo | LINQ provider returned `IQueryable<T>`; cast back to `IMongoQueryable<T>` for `ToListAsync` to work without ambiguity |

## Modifying or removing a Mongo entity (no scripts)

Whenever a Mongo-backed feature is modified or deleted, the changes touch
multiple coordinates: collection registration in the DbContext, indexes,
custom repositories, embedded references, and — most importantly —
**the data already in MongoDB**. These are done by hand because the
right answer depends on what else points at the collection.

### Add a property used as a filter

| File | Change |
|---|---|
| Entity | Add property (no `[BsonRepresentation]` for enums — the convention handles it; see "Storing enums as strings") |
| `Get{Entities}Input.cs` | Add nullable filter property |
| `{Entity}AppService.ApplyFilters` | Add LINQ `Where` clause |
| `{Entity}IndexInitializer` | Add index if the filter is high-cardinality / frequently used |
| Existing data | Field is missing on existing docs → LINQ `null`. The filter clause `c.X.HasValue` correctly skips them. Backfill if needed. |

### Rename a collection or change its `CollectionName`

The driver name and the on-disk name diverge. Three options:

1. **Rename the collection** in Mongo to match the new name:
   `db.OldName.renameCollection("NewName")`. Single-shot, downtime.
2. **Keep on-disk name, change C#** `[BsonElement]` / `b.CollectionName`
   to point at the old name. Cheaper.
3. **Dual-read** for a transition: keep the old collection accessible
   via a fallback. Rarely worth it.

Always surface the data choice to the user — never run the rename
silently. The reverse migration is not free.

### Switch a property's storage type

Examples: `int` → `long`, `string` → `Guid`, or enum representation.

The driver reads whatever's in BSON and trusts the C# type. Mismatches
throw `FormatException` at deserialization time. Plan a migration:

```javascript
// Example: backfill a missing field with a default
db.Customers.updateMany(
  { Country: { $exists: false } },
  { $set: { Country: "IT" } }
);

// Example: rename a field
db.Customers.updateMany({}, { $rename: { "LegalName": "RegisteredName" } });

// Example: integer enum → string enum (only needed if you previously
// stored as int and just now turned on EnumRepresentationConvention)
const statusNames = ["Prospect", "Active", "Churned"];
db.Customers.find({ Status: { $type: "int" } }).forEach(doc => {
  db.Customers.updateOne(
    { _id: doc._id },
    { $set: { Status: statusNames[doc.Status] } }
  );
});
```

### Remove an entity from the DbContext

When `abp-feature-dev` is removing a feature, the Mongo side is two
edits in `*MongoDbContext.cs`:

1. Remove the `IMongoCollection<{Entity}> {Plural}` property
2. Remove the `modelBuilder.Entity<{Entity}>(b => { ... })` block in
   `CreateModel`

Then delete (paths per template — `--show-layout` confirms them):
- The index initializer: nolayers `{{PROJECT_ROOT}}/Data/{Entity}IndexInitializer.cs`,
  layered `{{DOMAIN_PROJECT}}/{Plural}/{Entity}IndexInitializer.cs` (if it exists)
- The custom repository: nolayers `{{PROJECT_ROOT}}/Data/{Plural}/`,
  layered `{{DATA_PROJECT}}/MongoDb/{Plural}/` (if any), plus its interface in
  the Domain project on layered
- The `AddRepository<{Entity}, ...>` line in `*Module.cs` if the custom
  repo was registered

**The MongoDB collection on disk stays.** Surface to the user:

```
The Mongo collection `{Plural}` still contains N documents. To clean up:
  db.{Plural}.drop()
This is destructive — only run when you're sure no other app reads it.
```

Don't run `drop()` automatically, even if Claude has direct Mongo access.
The user might have a backup workflow, an analytics pipeline, or another
service that still reads the collection.

### Drop an index

After `verify_enum_string_setup.py` or any schema change, an old index
may become useless. Use `db.{Plural}.dropIndex("name")` — pass the
**name**, not the key spec. Indexes are inexpensive to recreate via
the `IndexInitializer`; the only cost is the first rebuild scan.

## What this skill does NOT cover

- **Atlas-specific topics** (Atlas Search, Vector Search, Stream Processing).
  Use the `mongodb:*` skills for that.
- **Schema design** (when to embed, when to reference, time-series patterns).
  That's `mongodb:mongodb-schema-design`.
- **Query optimization / indexes for performance.** That's
  `mongodb:mongodb-query-optimizer`.

This skill is specifically about the ABP integration layer: contexts,
repositories, ABP-specific quirks.
