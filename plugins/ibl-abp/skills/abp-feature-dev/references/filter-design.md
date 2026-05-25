# Smart filter design

The default "give me a `PagedAndSortedResultRequestDto` with a `Filter` string
field" is the lazy answer — it pushes complexity onto the client and forces
every list endpoint to LIKE-match against three columns. We can do better by
**inferring the right filters from the entity's property types** and
proposing them to the user.

This file documents the mapping. Treat it as the default; the user can extend
or override per-feature.

## Mapping property type → filter

| Property type | Proposed filter | Why |
|---|---|---|
| `string` (short identifier: Name, Code, Sku, TaxId) | `string? {Name}` (exact-insensitive **or** include in `Filter` text) | Short identifiers are usually queried for full matches or coarse text search |
| `string` (long: Description, Notes) | Included in `Filter` text-search only | Too long for an exact filter; expensive to "contains" individually |
| `enum` | `T? {Name}` | Nullable enum equality |
| `bool` | `bool? {Name}` | Three states: yes / no / either |
| `DateTime` / `DateTime?` | `DateTime? {Name}From`, `DateTime? {Name}To` | Range — never expose `=` on a timestamp |
| `int` / `long` / `decimal` / `double` (+ nullable) | `T? {Name}Min`, `T? {Name}Max` | Range |
| `Guid` foreign key | `Guid? {Name}` | Exact match — typically wired to a dropdown |
| Audit fields (`CreationTime`, `LastModificationTime`) | `DateTime? CreatedFrom/To`, `DateTime? ModifiedFrom/To` if requested | Only when the user explicitly cares about "show me records modified in this period" |

## The `Filter` text field

Every list endpoint gets one `string? Filter` field by default. Its job is the
quick "search box" in the UI. When applied it ORs across a curated subset of
fields — typically the human-readable names plus a primary identifier. Pick
the fields that make sense for **this** entity:

- For `Customer`: `LegalName`, `DisplayName`, `TaxId`
- For `Book`: `Name`, `Author`, `ISBN`
- For `Order`: `OrderNumber`, `CustomerName`

Avoid putting long-text fields (notes, descriptions) in the OR chain unless
they're indexed and the user really wants it — they kill performance on
MongoDB and SQL alike.

## The generated `Get{Entities}Input`

```csharp
using System;
using Ibl360.Entities.Customers;
using Volo.Abp.Application.Dtos;

namespace Ibl360.Services.Dtos.Customers;

public class GetCustomersInput : PagedAndSortedResultRequestDto
{
    /// <summary>
    /// Free-text search across LegalName, DisplayName, TaxId.
    /// </summary>
    public string? Filter { get; set; }

    public CustomerStatus? Status { get; set; }
    public CustomerSegment? Segment { get; set; }
    public string? Country { get; set; }
    public DateTime? CreatedFrom { get; set; }
    public DateTime? CreatedTo { get; set; }
}
```

XML doc-comments are valuable here — the Swagger UI surfaces them and they
help the frontend developer (often a different person) figure out the
contract without reading the controller.

## Applying filters in the AppService

For modest filter sets (<5 filters), inline LINQ in the `GetListAsync` method
is fine and keeps the code in one place:

```csharp
public async Task<PagedResultDto<CustomerDto>> GetListAsync(GetCustomersInput input)
{
    var query = await _repository.GetQueryableAsync();

    if (!string.IsNullOrWhiteSpace(input.Filter))
    {
        // Case-insensitive substring search. Both sides lowercased so the
        // user can type "acme" and still find "Acme S.p.A." — see the
        // "Case-insensitive text search" section below for the why/how.
        var f = input.Filter.Trim().ToLowerInvariant();
        query = query.Where(c =>
            c.LegalName.ToLower().Contains(f) ||
            c.DisplayName.ToLower().Contains(f) ||
            (c.TaxId != null && c.TaxId.ToLower().Contains(f)));
    }

    query = query
        .WhereIf(input.Status.HasValue, c => c.Status == input.Status!.Value)
        .WhereIf(input.Segment.HasValue, c => c.Segment == input.Segment!.Value)
        .WhereIf(!string.IsNullOrWhiteSpace(input.Country),
                 c => c.Country == input.Country!.Trim().ToUpperInvariant())
        .WhereIf(input.CreatedFrom.HasValue,
                 c => c.CreationTime >= input.CreatedFrom!.Value)
        .WhereIf(input.CreatedTo.HasValue,
                 c => c.CreationTime <= input.CreatedTo!.Value);

    var totalCount = await AsyncExecuter.CountAsync(query);

    query = query
        .OrderBy(input.Sorting.IsNullOrWhiteSpace() ? nameof(Customer.LegalName) : input.Sorting)
        .Skip(input.SkipCount)
        .Take(input.MaxResultCount);

    var items = await AsyncExecuter.ToListAsync(query);
    return new PagedResultDto<CustomerDto>(
        totalCount,
        ObjectMapper.Map<List<Customer>, List<CustomerDto>>(items));
}
```

## Case-insensitive text search (mandatory default)

`string.Contains` over LINQ translates to a **case-sensitive** match on both
MongoDB and EF Core / SQL collations that aren't explicitly case-insensitive.
The user typing "acme" then misses "Acme S.p.A." — silently empty list, looks
like a bug. Make case-insensitive search the **default** for every text
filter your AppService exposes:

```csharp
// AppService — apply both sides
var f = input.Filter!.Trim().ToLowerInvariant();
query = query.Where(c => c.LegalName.ToLower().Contains(f) || …);
```

### Why this works on MongoDB

The C# MongoDB LINQ provider translates `string.ToLower()` to the BSON
aggregation operator `$toLower`, and the wrapping `.Contains(f)` becomes a
`$regexMatch` over the lowercased field. The whole predicate stays a single
round-trip; nothing is enumerated client-side.

### Why this works on EF Core / SQL

EF Core translates `.ToLower()` to `LOWER(field)`. With most SQL collations
this is also a single round-trip. On databases with a case-insensitive
default collation (SQL Server `_CI_AS`, MySQL `utf8mb4_general_ci`) the
`ToLower()` is harmless but redundant — keep it anyway so the code is
correct under any collation.

### Performance note

A `LOWER(field)` predicate cannot use a regular B-tree index on the original
column. For collections that grow past ~50k rows AND have a hot text-search
endpoint, prefer one of:

- A **persisted lowercased field** (`LegalNameLower`) populated on
  `Insert`/`Update`, indexed normally — `query.Where(c => c.LegalNameLower.Contains(f))`
- A **MongoDB text index** (`db.Customers.createIndex({ LegalName: "text", DisplayName: "text" })`)
  queried via `Builders<T>.Filter.Text(f)` — case- and accent-insensitive
- A **PostgreSQL `pg_trgm` GIN index** on the lowercased column with
  `ILIKE`

The simple `.ToLower().Contains()` pattern is the right default; reach for
those index strategies only when you measure them as worth it.

### What to NOT do

- `string.Contains(f, StringComparison.OrdinalIgnoreCase)` — looks right,
  but the MongoDB LINQ provider does **not** translate the overload that
  takes a `StringComparison`. It either throws or silently falls back to
  client-side enumeration.
- `string.Equals(other, StringComparison.…)` — same problem.
- Custom `[BsonElement]` lowercasing tricks — opaque, easy to forget on
  the next entity.

Use the explicit `ToLower()` on both sides. It's verbose but unambiguous.

For larger filter sets (>5) **or** when the same filter shape is reused (export
+ list + delete-all), move the filter chain into a custom repository — see
`abp-mongodb` skill, `references/repositories.md`. The pattern: an `ApplyFilter`
method shared by `GetListAsync`, `GetCountAsync`, and `DeleteAllAsync`.

## Normalization rules to bake in

The smart-filter mapping is just type→shape. Normalization rules belong in
the **AppService** filter application (single source of truth):

- Trim whitespace on string inputs.
- Uppercase 2-letter ISO codes (Country = "it" → "IT").
- Lowercase email domains.
- Truncate ranges if `From > To` (return an empty result rather than throwing —
  some clients send inverted pickers).

These are noted in the AppService template's filter section.

## When to add an Owner / CreatorId filter

If the entity is per-user (each user can only see their own records), don't
expose `CreatorId` as a free-form filter — that lets one user query another
user's records by guessing their id. Instead, hardcode the filter to
`CurrentUser.Id` in the AppService. If admins need to see all records, add a
permission check that bypasses the filter for them:

```csharp
if (!await IsGrantedAsync(MyPermissions.Customers.SeeAll))
{
    query = query.Where(c => c.CreatorId == CurrentUser.Id);
}
```

## Things to avoid

- **A `Search`/`Filter` field with no documented columns.** The contract
  becomes opaque, the implementation drifts, and the frontend can't predict
  what the server will match.
- **Filter parameters that take regex.** Regex injection is a real concern;
  if the user needs glob-style matching, accept a prefix/suffix flag and
  build the predicate yourself.
- **Equality on `DateTime`.** Always range. Equality with a millisecond
  timestamp is never what the user wanted.
- **Sorting by arbitrary client-supplied column names.** Use
  `System.Linq.Dynamic.Core` with `OrderBy(input.Sorting)`, but constrain
  the allowed columns or sanitize — otherwise `Sorting = "Password desc"`
  could happen with a future column rename.
