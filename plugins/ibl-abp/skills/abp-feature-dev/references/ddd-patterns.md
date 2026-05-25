# DDD patterns in ABP

> Official: <https://abp.io/docs/latest/framework/architecture/domain-driven-design>

## Rich vs anemic domain model

ABP promotes a **rich** domain model — entities own both data and the behavior
that protects their invariants. The default `scaffold_entity.py` output is
deliberately rich (private setters, primary constructor, validation in the
constructor). Loosen it only for genuinely trivial CRUD records.

| Anemic | Rich |
|---|---|
| Public setters everywhere | Private setters; mutation via methods |
| Logic lives in services | Logic lives in entity methods |
| No validation in entity | Constructor + methods enforce invariants |

## Aggregate roots

An aggregate root:
- Is the consistency boundary for a cluster of related entities.
- Owns its child entities (which never have their own repository).
- Publishes domain events for side-effects.

```csharp
public class Order : AggregateRoot<Guid>
{
    public OrderStatus Status { get; private set; }
    public ICollection<OrderLine> Lines { get; private set; }

    protected Order() { }   // for ORM

    public Order(Guid id, string orderNumber, Guid customerId) : base(id)
    {
        OrderNumber = Check.NotNullOrWhiteSpace(orderNumber, nameof(orderNumber));
        CustomerId = customerId;
        Status = OrderStatus.Created;
        Lines = new List<OrderLine>();
    }

    public void AddLine(Guid lineId, Guid productId, int count, decimal price)
    {
        if (Status != OrderStatus.Created)
            throw new BusinessException("Orders:CannotModifyOrder");
        Lines.Add(new OrderLine(lineId, productId, count, price));
    }

    public void Complete()
    {
        if (Status != OrderStatus.Created)
            throw new BusinessException("Orders:CannotCompleteOrder");
        Status = OrderStatus.Completed;
        AddLocalEvent(new OrderCompletedEvent(Id));
        AddDistributedEvent(new OrderCompletedEto { OrderId = Id });
    }
}
```

### Local vs distributed events

- `AddLocalEvent` — handled in the same transaction; handler can see the full entity.
- `AddDistributedEvent` — published after the transaction commits; handlers
  receive an **ETO** (Event Transfer Object), defined in Domain.Shared so it can
  be referenced by other modules/services.

## Domain services (`*Manager`)

Use a domain service when business logic:
- spans multiple aggregates (validating uniqueness across them);
- needs repositories to enforce rules.

```csharp
public class OrderManager : DomainService
{
    private readonly IOrderRepository _orderRepo;
    public OrderManager(IOrderRepository orderRepo) => _orderRepo = orderRepo;

    public async Task<Order> CreateAsync(string orderNumber, Guid customerId)
    {
        if (await _orderRepo.FindByOrderNumberAsync(orderNumber) is not null)
            throw new BusinessException("Orders:OrderNumberAlreadyExists")
                .WithData("OrderNumber", orderNumber);

        return new Order(GuidGenerator.Create(), orderNumber, customerId);
    }
}
```

Conventions:
- Suffix the class with `Manager`.
- No interface unless you need one for testability / DI swapping.
- Accept and return domain objects (entities, value objects), never DTOs.
- Don't touch `CurrentUser` — let the application layer pass in the relevant ids.

## Repository pattern

- **Generic repository** (`IRepository<T, TKey>`) is enough for plain CRUD.
- **Custom repository** is only needed for custom query methods.
- **One repository per aggregate root.** Repositories for child entities break
  invariants by allowing callers to bypass the root.

```csharp
public interface IBookRepository : IRepository<Book, Guid>
{
    Task<Book?> FindByNameAsync(string name);
}
```

ABP MongoDB repositories: see the `abp-mongodb` skill.

## Specifications

Reusable, named query predicates:

```csharp
public class CompletedOrdersSpec : Specification<Order>
{
    public override Expression<Func<Order, bool>> ToExpression()
        => o => o.Status == OrderStatus.Completed;
}

var orders = await _orderRepo.GetListAsync(new CompletedOrdersSpec());
```

Specs compose (`spec1.And(spec2)`) and give you a single place to document what
a query means in business terms.

## Entity construction checklist

- [ ] `protected` parameterless constructor (for ORM)
- [ ] Primary constructor takes `Guid id` first (Guid created outside via `GuidGenerator`)
- [ ] Primary constructor enforces invariants (`Check.NotNullOrWhiteSpace`, etc.)
- [ ] Collections initialized in primary constructor
- [ ] All setters private; mutators are methods that validate
- [ ] Cross-aggregate references stored as `TKey` (no navigation properties to other aggregates)
- [ ] `virtual` on properties if you rely on EF Core lazy-loading proxies (rare in modern code)
