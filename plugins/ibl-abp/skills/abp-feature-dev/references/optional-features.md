# Optional platform features

The scaffolder can opt-in to several features that are common in admin/back-office
endpoints. None of them are added by default — the interview asks. This file
documents the pattern for each so you (and the scaffolder) can apply them
consistently.

## Concurrency stamp (optimistic locking)

**When to add it**: an entity is edited by many users, edit sessions are long
(forms open for minutes), or the cost of a lost update is high. For most
admin CRUD, **skip it** — the cost is a stamp the client must round-trip and
a 409 to handle.

**How**:

```csharp
public class Customer : AuditedAggregateRoot<Guid>, IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; } = default!;
    // ...
}
```

Update DTO carries the stamp the client received:

```csharp
public class UpdateCustomerDto : IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; } = default!;
    // ...
}
```

AppService passes it through:

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

ABP throws `AbpDbConcurrencyException` (mapped to HTTP 409 by default) when
stamps mismatch. The output DTO should include the current stamp so the
client can pass it back on the next update.

## Soft delete

**When to add it**: legal/audit requirements forbid hard delete, the entity
has dependent records that survive deletion, or accidental delete is a real
risk. **Skip it** for pure-lookup tables or genuinely ephemeral data.

**How**: inherit from `FullAuditedAggregateRoot<Guid>` instead of
`AuditedAggregateRoot<Guid>`:

```csharp
public class Customer : FullAuditedAggregateRoot<Guid>, IMultiTenant
{
    // FullAudited adds: DeleterId, DeletionTime, IsDeleted
}
```

ABP's `ISoftDelete` data filter is then automatic: `DeleteAsync` sets
`IsDeleted = true`; queries filter it out. To see deleted records (admin
recycle bin), disable the filter:

```csharp
using (DataFilter.Disable<ISoftDelete>())
{
    var deleted = await _repository.GetListAsync(c => c.IsDeleted);
}
```

To restore: load via the bypassed filter, set `IsDeleted = false`, call
`UpdateAsync`.

## Bulk delete

**When to add it**: admin UI needs "delete selected" or "delete all matching
filter" actions.

**How** — two methods on the AppService:

```csharp
[Authorize(Ibl360Permissions.Customers.Delete)]
public virtual async Task DeleteByIdsAsync(List<Guid> ids)
{
    await _repository.DeleteManyAsync(ids);
}

[Authorize(Ibl360Permissions.Customers.Delete)]
public virtual async Task DeleteAllAsync(GetCustomersInput input)
{
    // Reuse the same filter chain as GetListAsync — typically lives in a
    // private ApplyFilter method or in a custom repository.
    var queryable = await _repository.GetQueryableAsync();
    queryable = ApplyFilter(queryable, input);
    var ids = await AsyncExecuter.ToListAsync(queryable.Select(c => c.Id));
    await _repository.DeleteManyAsync(ids);
}
```

Both routes appear under the AppService automatically (`POST
/api/app/customer/delete-by-ids` and `.../delete-all`).

### Limits and confirmations

Add a soft cap if you don't trust the client (e.g. >1000 ids is suspicious):

```csharp
if (ids.Count > 1000)
    throw new BusinessException("{{ROOT_NAMESPACE}}:BulkLimitExceeded")
        .WithData("Limit", 1000)
        .WithData("Got", ids.Count);
```

For `DeleteAllAsync`, require the same filter to be sent in a separate
"confirm" step from the UI — the AppService can't know how dangerous a
filter is on its own.

## Excel export

**When to add it**: admin users need to download lists for offline analysis.

**How** — uses the `MiniExcel` package (lightweight, no Office dependency).

Add to `*.csproj` (only if it's not already there):

```xml
<PackageReference Include="MiniExcel" Version="1.34.2" />
```

DTOs:

```csharp
public class CustomerExcelDto
{
    public string LegalName { get; set; } = default!;
    public string DisplayName { get; set; } = default!;
    public string? TaxId { get; set; }
    public string Country { get; set; } = default!;
    public string Status { get; set; } = default!;  // localized enum text
    public DateTime CreationTime { get; set; }
}

public class CustomerExcelDownloadDto : GetCustomersInput  // reuses filter shape
{
    public string DownloadToken { get; set; } = default!;
}
```

A **download token** is required because the controller's auth doesn't apply
to file downloads triggered by a `<a href=...>` click — the browser doesn't
send the bearer token. The pattern: client first calls
`GetDownloadTokenAsync` (which **does** require auth), receives a short-lived
token, then includes it in the file-download URL.

```csharp
public class CustomerDownloadTokenCacheItem
{
    public string Token { get; set; } = default!;
}

public class DownloadTokenResultDto
{
    public string Token { get; set; } = default!;
}
```

AppService:

```csharp
private readonly IDistributedCache<CustomerDownloadTokenCacheItem, string> _tokenCache;

public async Task<DownloadTokenResultDto> GetDownloadTokenAsync()
{
    var token = Guid.NewGuid().ToString("N");
    await _tokenCache.SetAsync(token,
        new CustomerDownloadTokenCacheItem { Token = token },
        new DistributedCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = TimeSpan.FromSeconds(30)
        });
    return new DownloadTokenResultDto { Token = token };
}

[AllowAnonymous]
public async Task<IRemoteStreamContent> GetListAsExcelFileAsync(CustomerExcelDownloadDto input)
{
    var cached = await _tokenCache.GetAsync(input.DownloadToken);
    if (cached == null || cached.Token != input.DownloadToken)
        throw new AbpAuthorizationException("Invalid download token");

    var queryable = await _repository.GetQueryableAsync();
    queryable = ApplyFilter(queryable, input);
    var items = await AsyncExecuter.ToListAsync(queryable);

    var stream = new MemoryStream();
    var rows = ObjectMapper.Map<List<Customer>, List<CustomerExcelDto>>(items);
    await stream.SaveAsAsync(rows);
    stream.Position = 0;

    return new RemoteStreamContent(stream, "Customers.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
}
```

Notes:
- `[AllowAnonymous]` is required because the URL has no auth header — the
  token is the auth.
- 30s is a sensible token lifetime: enough for the browser to click and
  download, short enough that a leaked token is useless.

## Lookup endpoint (id + display)

**When to add it**: another entity references this one and the UI needs a
dropdown. Returning the full DTO is wasteful when you only need
`{ Id, DisplayName }`.

```csharp
public class CustomerLookupDto
{
    public Guid Id { get; set; }
    public string DisplayName { get; set; } = default!;
}

public class LookupRequestDto : PagedAndSortedResultRequestDto
{
    public string? Filter { get; set; }
}

[Authorize(Ibl360Permissions.Customers.Default)]
public async Task<PagedResultDto<CustomerLookupDto>> GetLookupAsync(LookupRequestDto input)
{
    var query = await _repository.GetQueryableAsync();

    if (!string.IsNullOrWhiteSpace(input.Filter))
    {
        var f = input.Filter.Trim();
        query = query.Where(c => c.DisplayName.Contains(f) || c.LegalName.Contains(f));
    }

    var total = await AsyncExecuter.CountAsync(query);
    var items = await AsyncExecuter.ToListAsync(
        query.OrderBy(c => c.DisplayName)
             .Skip(input.SkipCount)
             .Take(input.MaxResultCount)
             .Select(c => new CustomerLookupDto { Id = c.Id, DisplayName = c.DisplayName }));

    return new PagedResultDto<CustomerLookupDto>(total, items);
}
```

The lookup endpoint uses the **default permission** (anyone who can see the
list can populate a dropdown). If you have a tighter requirement, add a
`Lookup` permission.

## Custom repository (typed filter methods)

**When to add it**: more than ~5 filters, the same filter shape is reused
across endpoints (list + export + delete-all), or you need an operator the
generic `GetQueryableAsync()` LINQ chain doesn't express cleanly.

See the `abp-mongodb` skill (`references/repositories.md`) for the full
pattern. The short version:

```csharp
public interface ICustomerRepository : IRepository<Customer, Guid>
{
    Task<List<Customer>> GetListAsync(/* typed filter args */, string? sorting, int max, int skip, CancellationToken ct = default);
    Task<long> GetCountAsync(/* typed filter args */, CancellationToken ct = default);
    Task DeleteAllAsync(/* typed filter args */, CancellationToken ct = default);
}

public class MongoCustomerRepository
    : MongoDbRepository<Ibl360DbContext, Customer, Guid>, ICustomerRepository
{
    protected IQueryable<Customer> ApplyFilter(IQueryable<Customer> q, /* args */)
    {
        return q
            .WhereIf(!string.IsNullOrWhiteSpace(filter), c => /* … */)
            .WhereIf(status.HasValue, c => c.Status == status.Value);
    }
    // … methods that all start with `ApplyFilter(query, …)`
}
```

Register it in the MongoDb module:

```csharp
context.Services.AddMongoDbContext<Ibl360DbContext>(options =>
{
    options.AddDefaultRepositories();
    options.AddRepository<Customer, MongoCustomerRepository>();
});
```

## When to combine features

- Bulk delete + soft delete: bulk-`DeleteAsync` correctly soft-deletes when
  `ISoftDelete` is on the entity. No special handling.
- Excel export + multi-tenancy: the data filter applies to the export query
  too, automatically.
- Concurrency stamp + bulk delete: skip the stamp on bulk — there's no way
  for the client to send one stamp for many entities.
- Lookup + bulk delete: the same filter shape; if you have both, keep them
  consistent (`Get{Entities}Input` reused everywhere).
