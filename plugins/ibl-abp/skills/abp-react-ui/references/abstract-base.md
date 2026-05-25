# Abstract base class — UI side

When two entities share most of their fields (Customer + Supplier in
IBL360; Lead + Customer in many CRMs; AccountsPayable + AccountsReceivable
in many ERPs), the backend usually models them with a shared abstract
class. The UI should follow suit so the two pages don't drift.

Anchor example: **Customer** and **Supplier** in IBL360 both extend
`BusinessParty` on the backend; the React side mirrors that.

## TypeScript shape

Put the shared shape in a dedicated module that both API clients
re-export from:

```
react/src/lib/api/
├── businessParty.ts    ← shared types + enum option arrays
├── customers.ts         ← extends BusinessPartyDtoBase + RelationshipType
└── suppliers.ts         ← extends BusinessPartyDtoBase (no extras)
```

```ts
// businessParty.ts
export interface BusinessPartyDtoBase {
  id: string
  legalName: string
  // …every shared field…
}

export interface BusinessPartyCreateUpdateDtoBase {
  legalName: string
  // …every shared input field…
}
```

```ts
// customers.ts
import type { BusinessPartyDtoBase, BusinessPartyCreateUpdateDtoBase } from './businessParty'

export interface CustomerDto extends BusinessPartyDtoBase {
  relationshipType: RelationshipType
}
export interface CreateUpdateCustomerDto extends BusinessPartyCreateUpdateDtoBase {
  relationshipType: RelationshipType
}
```

**Re-export aliases** for backward compatibility when you unify enums
that previously had per-entity names:

```ts
export type { PartyStatus, PartySegment } from './businessParty'
export { partyStatusOptions as customerStatusOptions } from './businessParty'

// Keeps old code that imports CustomerStatus building until you migrate it.
export type CustomerStatus = PartyStatus
```

## Reusable UI components

The whole point of unifying types is to unify the UI that consumes
them. For every shared "tab" (Contact, Addresses, Financial,
Communication, CustomFields), extract a component once and reuse it
in both edit pages.

See `complex-edit-page.md` for the catalogue of components
(`PostalAddressFields`, `SocialsEditor`, `ShippingAddressesEditor`,
`CommPrefsEditor`, `CustomFieldsEditor`) plus `EditPageShell` +
`TabsStrip` for the chrome.

The two edit pages then differ ONLY where the entities differ. For
Customer/Supplier in IBL360 that's:
- Customer's `general` tab has a `relationshipType` Select.
- Supplier's `statusRelation` tab has only `CommPrefsEditor` (no
  relationship-type field).

Everything else is verbatim shared. The two files are ~600 lines each
but the unique surface is ~30 lines per page.

## Don't extract a generic `<BusinessPartyEditPage>` component

You'll be tempted. Resist for at least one more entity.

Two reasons:

1. **Schema divergence**: a third entity (Vendor, Lead, Branch) usually
   needs ONE field the other two don't, and trying to parameterise the
   abstract page leads to prop drilling + conditional rendering inside
   the shared component. Worse than duplication.

2. **Form library state**: react-hook-form's `useForm<T>()` is generic
   in the form data type. A "generic" page would need either `any`
   (lose type safety) or a complex generic prop interface
   (`<EditPage<T, S, C, ...>>` with 4 generics). Concrete pages with
   their own schema + form keep the types honest.

The rule: **share the chrome and the field-group components, keep the
page concrete**. Two pages, three pages, four — when you genuinely
need a fifth, then consider the abstract page (with a clear plan for
how it'll handle the entity-specific fields).

## Defaults at the form level, not the page level

When the backend has `RelationshipType` that defaults to `Customer`,
the page's `defaultValues()` helper should write that default — NOT
the form-control component. This way the same form helper can be
used by other pages that don't have RelationshipType, and you don't
end up with conditional defaults sprinkled across multiple files.

```ts
// CustomerEditPage.tsx
function defaultValues(): CustomerFormData {
  return {
    // …shared defaults…
    segment: 'Smb',
    relationshipType: 'Customer',  // Customer-only field, default here
  }
}
```

## DTO ↔ form conversion: helpers per page

Each edit page has two helpers that don't translate:
`fromDto(dto): FormData` and `toDto(form): CreateUpdateDto`. Don't try
to share these — they're load-bearing and benefit from per-entity
specificity (empty-string normalization, address VO collapse to null,
list filtering of incomplete rows).

The 80% inside both helpers is the same shape, but every entity has
one or two fields that need bespoke handling. Sharing makes the
helpers grow conditional logic; duplicating keeps them readable.

## When this pattern stops paying off

If you find that 3+ entities all need the same shape AND the same
defaults AND the same DTO↔form conversion, you're at the threshold
where a shared page might be worth it. By that point you'll also
have enough constraints (and edge cases) documented to do it right.

Until then: shared types, shared field components, concrete pages.
