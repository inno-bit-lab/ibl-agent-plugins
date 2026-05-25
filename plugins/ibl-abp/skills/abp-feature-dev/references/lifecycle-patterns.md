# Lifecycle / state machine patterns

Many domain entities have a `Status` or `State` field with a small set of
allowed values and an even smaller set of allowed transitions between them.
This is a **finite state machine** — and modelling it as such inside the
entity catches a whole class of bugs at compile + run-time.

This file describes the pattern the scaffolder produces when the interview
identifies a lifecycle.

## When you have a lifecycle (and when you don't)

You have a lifecycle when:
- The field is an enum (or string CHECK constraint) with a small fixed set.
- Some transitions are forbidden ("a `Churned` customer cannot become
  `Prospect` again without explicit reactivation").
- Time-of-transition matters ("when did this customer become active?").
- Side effects fire on transition (email, event, audit row).

You **don't** have a lifecycle when:
- The field is a free-form tag the user can change anytime.
- All transitions are equally valid.
- Nothing depends on the timestamp of the change.

## The pattern

Three pieces in the entity:

1. **`Status` enum property** with private setter.
2. **`StatusChangedAt`** timestamp (nullable — null until the first
   transition).
3. **`ChangeStatus(newStatus, IClock)`** method that validates the
   transition, updates both fields atomically, and throws a
   `BusinessException` on an invalid transition.

```csharp
public class Customer : AuditedAggregateRoot<Guid>, IMultiTenant
{
    public Guid? TenantId { get; set; }

    public CustomerStatus Status { get; private set; }
    public DateTime? StatusChangedAt { get; private set; }
    // … other fields …

    protected Customer() { }

    public Customer(Guid id, /* … */) : base(id)
    {
        // … field initialization …
        Status = CustomerStatus.Prospect;   // initial state
        StatusChangedAt = null;
    }

    public void ChangeStatus(CustomerStatus newStatus, IClock clock)
    {
        Check.NotNull(clock, nameof(clock));

        if (newStatus == Status) return;       // idempotent — no-op

        if (!IsValidTransition(Status, newStatus))
            throw new BusinessException(
                Ibl360DomainErrorCodes.Customers.InvalidStatusTransition)
                .WithData("From", Status)
                .WithData("To", newStatus);

        Status = newStatus;
        StatusChangedAt = clock.Now;
    }

    private static bool IsValidTransition(CustomerStatus from, CustomerStatus to)
        => (from, to) switch
        {
            (CustomerStatus.Prospect, CustomerStatus.Active)   => true,
            (CustomerStatus.Active,   CustomerStatus.Churned)  => true,
            _ => false
        };
}
```

The switch expression is the **source of truth for the state machine**. To
add a transition you edit one line.

## The AppService endpoint

A dedicated `ChangeStatusAsync` endpoint, separate from the generic
`UpdateAsync`:

```csharp
public class ChangeCustomerStatusDto
{
    [Required]
    public CustomerStatus NewStatus { get; set; }
}

[Authorize(Ibl360Permissions.Customers.Edit)]
public async Task<CustomerDto> ChangeStatusAsync(Guid id, ChangeCustomerStatusDto input)
{
    var customer = await _repository.GetAsync(id);
    customer.ChangeStatus(input.NewStatus, Clock);
    await _repository.UpdateAsync(customer);
    return ObjectMapper.Map<Customer, CustomerDto>(customer);
}
```

Why a separate endpoint?
- The frontend's UX usually has a dedicated control for status changes
  (workflow button, dropdown with confirmation modal) — distinct from the
  edit form.
- The `Update` endpoint stays simple: it doesn't have to know that
  `Status` is special.
- Permissions can differentiate ("can edit fields" vs "can change
  lifecycle") if needed later — just split the policy.

## Domain error codes

Errors thrown from the entity (`BusinessException`) need a localized
message. The codes go in a dedicated file at the project root:

```csharp
// Ibl360DomainErrorCodes.cs
namespace Ibl360;

public static class Ibl360DomainErrorCodes
{
    public static class Customers
    {
        public const string InvalidStatusTransition = "Ibl360:Customers:InvalidStatusTransition";
    }
}
```

The corresponding entry in `Localization/Ibl360/it.json`:

```json
"Ibl360:Customers:InvalidStatusTransition":
    "Transizione di stato non valida da {From} a {To}."
```

And `en.json`:

```json
"Ibl360:Customers:InvalidStatusTransition":
    "Invalid customer status transition from {From} to {To}."
```

The `{From}` / `{To}` placeholders come from the `.WithData(...)` call. ABP
maps these into the message at the time of localization.

## Side effects on transition (events)

When the transition needs to trigger something else (send an email, notify
billing, publish to other modules), use domain events:

```csharp
public void ChangeStatus(CustomerStatus newStatus, IClock clock)
{
    // … validation as before …
    var previous = Status;
    Status = newStatus;
    StatusChangedAt = clock.Now;
    AddLocalEvent(new CustomerStatusChangedEvent(Id, previous, newStatus));
    AddDistributedEvent(new CustomerStatusChangedEto { CustomerId = Id, From = previous, To = newStatus });
}
```

- **Local event**: handled in the same transaction. Useful for triggering
  a related repository update.
- **Distributed event**: handled after commit. Useful for cross-module
  reactions or external integrations.

See `references/ddd-patterns.md` for the broader event story.

## Initial state and the constructor

The initial state goes in the primary constructor. **Don't** accept it as a
parameter — that would let a caller create a `Customer` already in the
`Churned` state, which makes no business sense and bypasses the state
machine entirely.

```csharp
// ❌ Wrong: caller chooses the starting state
public Customer(Guid id, /* … */, CustomerStatus status) : base(id)
{
    Status = status;
}

// ✅ Right: starting state is a property of the type
public Customer(Guid id, /* … */) : base(id)
{
    Status = CustomerStatus.Prospect;
}
```

If you genuinely need to seed an entity at a non-initial state (importing
historical data), do it via a dedicated **import** code path — not the
production constructor.

## Tests

The `abp-testing` skill scaffolds these baseline tests when the entity has a
lifecycle:

- `Should_Initialize_With_{InitialState}` — new entity has the right initial
  state and `StatusChangedAt == null`.
- `Should_Change_From_{From}_To_{To}` — happy path for each valid transition.
- `Should_Throw_On_Invalid_Transition` — covers a representative bad
  transition (e.g. Prospect → Churned).
- `Should_Be_Idempotent_When_Transitioning_To_Same_State` — calling
  `ChangeStatus(current)` is a no-op.
- `Should_Update_StatusChangedAt_To_Clock_Now` — uses a substituted
  `IClock` to verify the timestamp.

## When to use IClock vs Clock property

The pattern uses `IClock clock` as a method parameter — not the `Clock`
property — because the entity is **not** an ABP base class and doesn't have
a `Clock` property. The AppService passes its `Clock` property in:

```csharp
customer.ChangeStatus(input.NewStatus, Clock);
```

This keeps the entity testable in isolation: pass a substituted
`Clock = Substitute.For<IClock>()` that returns a known timestamp.

If you find this verbose, an alternative is a static `Clock` accessor (some
ABP versions provide `IClock` via service locator), but the explicit
parameter is clearer and well-supported by tests.
