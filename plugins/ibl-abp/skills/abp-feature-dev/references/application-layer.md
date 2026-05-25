# Application layer patterns

> Official: <https://abp.io/docs/latest/framework/architecture/domain-driven-design/application-services>

## Application Service responsibilities

An Application Service orchestrates a single use case:
1. Validates input DTOs (data annotations / FluentValidation / `IValidatableObject`).
2. Checks authorization (`[Authorize]` or `CheckPolicyAsync`).
3. Loads aggregates via repositories.
4. Delegates business decisions to entity methods or domain services.
5. Persists changes (explicit `UpdateAsync` for non-tracked providers).
6. Returns DTOs.

It is **not** the place for business rules — those belong in the entity or
domain service. If your AppService has more than a couple of `if`s about
business state, the logic wants to move down.

## Naming conventions for DTOs

| Purpose | Convention | Example |
|---|---|---|
| Query input | `Get{Entity}Input` | `GetBookInput` |
| List query input | `Get{Entity}ListInput` | `GetBookListInput` |
| Create input | `Create{Entity}Dto` | `CreateBookDto` |
| Update input | `Update{Entity}Dto` | `UpdateBookDto` |
| Single output | `{Entity}Dto` | `BookDto` |
| List item output | `{Entity}ListItemDto` | `BookListItemDto` |

The scaffolder uses a single `CreateUpdate{Entity}Dto` for both create and
update, which matches the `CrudAppService<...>` base. Split them when create
and update have meaningfully different shapes (e.g. update accepts a partial,
create requires everything).

## Things AppServices should NOT do

- Repeat the entity name in method names (`GetAsync`, not `GetBookAsync`).
- Return entities. Always map to DTOs.
- Accept `IFormFile` or `Stream` — let the controller turn those into `byte[]`.
- Take an `id` as part of an `UpdateDto`. Pass it as a separate parameter.
- Call other AppServices in the same module. Use a domain service or event.
- Inject services that are already properties of the base class
  (`Clock`, `CurrentUser`, `GuidGenerator`, `L`, `AuthorizationService`,
  `FeatureChecker`).

## Validation

Decide first: **domain rule** or **application rule**?

- **Domain rule** (entity invariant, business law): enforce in the entity
  constructor or domain service. The application layer should not be able to
  bypass it.
- **Application rule** (input format, missing field): validate the DTO.

Three styles, pick what suits the rule:

```csharp
// Data Annotations — for simple per-field rules
public class CreateBookDto
{
    [Required, StringLength(100, MinimumLength = 3)]
    public string Name { get; set; }

    [Range(0, 999.99)]
    public decimal Price { get; set; }
}

// IValidatableObject — for cross-field rules within one DTO
public class CreateBookDto : IValidatableObject
{
    public IEnumerable<ValidationResult> Validate(ValidationContext ctx)
    {
        if (Name == Description)
            yield return new ValidationResult("Name and Description must differ",
                new[] { nameof(Name), nameof(Description) });
    }
}

// FluentValidation — for complex / reusable validators
public class CreateBookDtoValidator : AbstractValidator<CreateBookDto>
{
    public CreateBookDtoValidator()
    {
        RuleFor(x => x.Name).NotEmpty().Length(3, 100);
        RuleFor(x => x.Price).GreaterThan(0);
    }
}
```

## Exceptions and HTTP mapping

| Throw | Typical HTTP |
|---|---|
| `AbpValidationException` (auto from data-annotation/IValidatable/FluentValidation) | 400 |
| `AbpAuthorizationException` | 401 / 403 |
| `EntityNotFoundException(typeof(Book), id)` | 404 |
| `BusinessException("Module:Code").WithData(...)` | 403 (configurable) |
| `UserFriendlyException(L["MessageKey"])` | 4xx, localized message |
| Anything else | 500 |

Mapping is configurable — don't rely on the default code in business logic.

## Object mapping: Mapperly (default) or AutoMapper

Check what the solution already uses before introducing a new mapper. Most
modern ABP solutions use **Mapperly** (compile-time, faster, type-safe).

```csharp
[Mapper]
public partial class BookMapper
{
    public partial BookDto MapToDto(Book book);
    public partial List<BookDto> MapToDtoList(List<Book> books);
}
```

Register as singleton:

```csharp
context.Services.AddSingleton<BookMapper>();
```

If the solution still uses AutoMapper, write a `Profile`:

```csharp
public class BookApplicationAutoMapperProfile : Profile
{
    public BookApplicationAutoMapperProfile()
    {
        CreateMap<Book, BookDto>();
        CreateMap<CreateBookDto, Book>();
    }
}
```

Don't mix the two within one feature — pick whichever the rest of the
solution uses.

## Auto API Controllers

When an interface inherits `IApplicationService`, ABP exposes it as a REST
controller automatically. Method-name prefixes drive HTTP verbs:

| Prefix | Verb |
|---|---|
| `Get` | GET |
| `Create` | POST |
| `Update` | PUT |
| `Delete` | DELETE |

Disable for a specific method with `[RemoteService(false)]` or for the whole
service with `[RemoteService(IsEnabled = false)]`.

For non-default conventions or finer control, write a real `AbpController`
that delegates to the AppService.
