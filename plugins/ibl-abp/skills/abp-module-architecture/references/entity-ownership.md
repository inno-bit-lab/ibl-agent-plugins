# Entity Ownership

Use this checklist to decide where an ABP entity belongs before scaffolding or
moving it.

## Ownership Rules

| Signal | Placement |
|---|---|
| Entity is a core business concept with its own lifecycle, permissions, pages, and persistence | Bounded-context module |
| Entity is reused by multiple bounded contexts as a base type, enum, DTO fragment, value object, or UI primitive | Shared module |
| Entity exists only to compose the host app, auth, tenant bootstrap, app users, or deployment/runtime integration | Host |
| Entity is used by exactly one module but "might be useful later" | Keep in that module |
| UI component is reused by multiple modules | Shared React UI |
| UI page/API/client belongs to one domain area | That module's React folder |

## Shared Module Bar

Shared is a shared kernel, not a dumping ground. Put code in `Shared` only when
all of these hold:

- At least two bounded contexts need the same abstraction now.
- The abstraction has stable semantics across those contexts.
- Depending on Shared does not force either module to import another module's
  implementation.
- The name is domain-neutral enough to survive a second consumer.

Examples:

- `BusinessParty`, `PostalAddress`, `PartyStatus`, shared DTO bases, and shared
  form editors can live in Shared if both CRM Customer and Supplier use them.
- `Customer`, `Supplier`, `Account`, and `Contact` stay in CRM.
- `Employee` stays in HR or host until an HR module exists.

## Dependency Direction

Allowed:

- Host depends on modules.
- Feature modules depend on Shared contracts/domain abstractions.
- React host imports module UI through a registry.
- Module UI imports Shared UI primitives.

Avoid:

- Shared depending on a feature module.
- One feature module importing another feature module's implementation.
- Host owning domain permission namespaces for module-owned features.
- React module pages living in the host while backend lives in a module.

## Naming

Use module-owned namespaces and codes consistently:

- Backend namespace: `Ibl360Crm.Services.Customers`
- Permission group: `Ibl360Crm`
- Permission name: `Ibl360Crm.Customers`
- Error code: `Ibl360Crm:Customers:InvalidStatusTransition`
- Localization resource: `Ibl360Crm`
- React package alias: `@ibl360/crm-ui`

Do not keep old host names as compatibility shims unless there is a real
external API compatibility requirement and a migration plan.
