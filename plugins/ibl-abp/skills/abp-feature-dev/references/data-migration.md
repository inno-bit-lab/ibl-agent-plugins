# Data migration during backend refactor

When the schema changes and the database is not empty, the C# build
green-lighting does NOT mean the migration is done. This reference
covers the moves that have caught us in IBL360 and how to do them
safely.

## The four classes of refactor

| Refactor | Code? | Data? | Indexes? | Permissions? |
|---|---|---|---|---|
| Add a new optional field | ✓ | — | ± | — |
| Add a new required field | ✓ | **migrate or default** | ± | — |
| Rename a field | ✓ | **rename or accept N/A on old docs** | rename | — |
| **Remove an enum value (e.g. CustomerStatus.Prospect)** | ✓ | **CRITICAL: updateMany to remap existing docs** | — | — |
| **Rename or unify two enums (CustomerStatus + SupplierStatus → PartyStatus)** | ✓ | **identity migration if old/new names match; otherwise remap** | — | — |
| Remove an entity (e.g. SupplierContact) | ✓ | **migrate or drop** | drop | **drop grants** |
| Move a flat field into a VO (Country → BillingAddress.Country) | ✓ | **migrate or accept null on old docs** | drop+recreate w/ new path | — |
| Split an entity (Contact owning Customer FK only → Contact owning Customer OR Supplier FK) | ✓ | **migrate FK / merge data from sibling collection** | rebuild | unify perms |

The "Data?" column is the one that gets forgotten. Build green +
restart green ≠ refactor green. Walk the DB before declaring done.

### The enum-removal trap (real case)

Removing a value from an enum that's persisted as a BSON string makes
the C# Mongo driver throw `FormatException: Requested value 'X' was
not found` on the next deserialize. The query itself never returns;
the entire list endpoint returns HTTP 500.

The trap: this fails ONLY at read time, never at build time. The
backend boots fine. Smoke-testing only works if there's at least one
document with the removed enum value in the collection — and dev
databases often have none, hiding the bug until production.

**Mandatory remediation step when removing or renaming an enum value:**

```js
// In mongo shell, or via the MongoDB MCP `update-many`:
db.Customers.updateMany(
  { Status: "Prospect" },              // removed value
  { $set: { Status: "Active",          // new lifecycle home
            RelationshipType: "Prospect" } }  // new semantic home (Customer-only)
)
db.Suppliers.updateMany(
  { Status: "Prospect" },
  { $set: { Status: "Active" } }       // Supplier has no RelationshipType
)
```

Plus a sanity sweep AFTER the remap:

```js
// Find anything still on a value the new enum doesn't accept.
db.Customers.countDocuments({ Status: { $nin: ["Active", "OnHold", "Churned"] } })
db.Suppliers.countDocuments({ Status: { $nin: ["Active", "OnHold", "Churned"] } })
// Both must be 0.
```

If you can't enumerate the legal values (e.g. very large enum),
filter the OPPOSITE — find any doc whose Status is NOT one of the
canonical names you just listed.

### The new-required-field trap (real case)

Adding a non-nullable field (e.g. RelationshipType on Customer)
**does NOT crash the deserializer immediately** because the C#
default is the enum's first member (numerical value 0, i.e. the
first declared value). But you'll see two surprises:

1. Existing documents silently get the default value, which is
   probably not what you want (every legacy customer becomes
   `RelationshipType=Customer` regardless of their actual nature).
2. If the field is rendered in the UI as a Select, the dropdown
   may show no selection because the BSON doc has no key at all
   — only after the first edit-and-save the value materializes.

Best practice: **explicitly set the field on legacy docs at the
time you add it** with an `updateMany` covering the default
semantic value:

```js
db.Customers.updateMany(
  { RelationshipType: { $exists: false } },
  { $set: { RelationshipType: "Customer" } }
)
```

Plus the sanity sweep:

```js
db.Customers.countDocuments({ RelationshipType: { $exists: false } })
// Must be 0.
```

### The remove-flat-field trap (real case)

When a flat field becomes a VO (e.g. `Country` → `BillingAddress.Country`),
the C# class no longer has a `Country` property. Mongo's default
deserializer is forgiving (extra fields are ignored) — but ABP's
`AbpBsonClassMap` configurations vary. The cleanup pays for itself
either way and removes future confusion:

```js
db.Customers.updateMany(
  { $or: [ { Country: { $exists: true } }, { Address: { $exists: true } } ] },
  { $unset: { Country: "", Address: "" } }
)
db.Suppliers.updateMany(
  { $or: [ { Country: { $exists: true } }, { Address: { $exists: true } } ] },
  { $unset: { Country: "", Address: "" } }
)
```

### Mandatory checklist for any refactor that touches a persisted enum, field, or shape

Before declaring the refactor done, run this in the mongo shell or
via the MongoDB MCP:

```js
// For each collection of the refactored entity:
// 1. Find documents with the old enum value(s):
db.X.countDocuments({ <field>: <oldValue> })  // must be 0

// 2. Find documents with the new field MISSING (if newly added):
db.X.countDocuments({ <newField>: { $exists: false } })  // 0 or accept defaults

// 3. Find documents with values NOT in the new enum's allowed set:
db.X.countDocuments({ <field>: { $nin: [<all valid values>] } })  // must be 0

// 4. Find documents with stale flat fields (if moved into a VO):
db.X.countDocuments({ <oldFlatField>: { $exists: true } })  // 0 or accept ignored
```

All four must return 0 (or "accept defaults" for #2). If any is
non-zero, the refactor has uncovered data — write the updateMany
NOW, not later.

## Stop the backend before you touch the DB

The dev-mode backend caches schema, holds the apphost lock, and
sometimes has open cursors. Run any migration with the backend OFF:

```
# 1. Stop backend (Stop-Process / pkill on the apphost + dotnet run)
# 2. Build (regenerates apphost.exe — needed by dotnet run --no-build later)
# 3. Run --migrate-database
# 4. Restart the backend (and only then test)
```

The `abp-feature-dev` skill ships with this sequence already documented
in SKILL.md "Build flags gotcha".

## Adding fields with defaults

Just add the field. MongoDB returns `null` (or the type's default for
`bool`/`int`) for documents that don't have it; the C# deserializer
handles that natively for nullable reference types and
`Nullable<value type>`. For enums, you must opt in to safe handling:

```csharp
// Existing docs without the field will deserialize the enum's default value (0).
// If that's wrong, run a one-shot updateMany BEFORE deploying:
db.Customers.updateMany(
  { RelationshipType: { $exists: false } },
  { $set: { RelationshipType: "Customer" } }
)
```

## Renaming a field

In a flat doc:

```js
db.Customers.updateMany(
  { OldFieldName: { $exists: true } },
  { $rename: { OldFieldName: "NewFieldName" } }
)
```

In a nested doc:

```js
db.Customers.updateMany(
  { "BillingAddress.OldField": { $exists: true } },
  { $rename: { "BillingAddress.OldField": "BillingAddress.NewField" } }
)
```

## Removing an entity completely

This is the order that does NOT leave orphan rows / dangling
references behind. SupplierContact removal in IBL360 followed it:

1. **Inspect** the collection: how many docs? Are any of them worth
   migrating to a sibling entity?
   ```js
   db.SupplierContacts.countDocuments()
   db.SupplierContacts.findOne()
   ```
2. **Migrate the worth-keeping docs** to the new home (see "Cross-
   collection migration" below).
3. **Drop the collection**:
   ```js
   db.SupplierContacts.drop()
   ```
4. **Delete the permission grants** for the removed permission tree.
   They become orphan rows otherwise (harmless but ugly in the
   admin permission tree):
   ```js
   db.AbpPermissionGrants.deleteMany({
     Name: { $regex: "^Ibl360\\.SupplierContacts" }
   })
   ```
5. **Remove the permission definition from the
   PermissionDefinitionProvider** and the constants from `*Permissions.cs`.
6. **Remove the seed contributor grants** for the deleted
   permissions (otherwise the next `migrate-database` re-creates the
   grants you just deleted in step 4).

Steps 4–6 don't have a "build error" feedback loop. They have to be
done from memory or from a written checklist. **This is what the
checklist is for.**

## Cross-collection migration (when an entity merges into another)

Example: SupplierContact → Contact (refactored to support both
CustomerId? and SupplierId?). The IBL360 flow:

1. **Read the source docs** with the MongoDB MCP / Compass / shell.
2. **Insert into the target collection** with the field mapping
   spelled out (Email lowercased, IsPrimary → IsPrimaryForSupplier,
   add `IsPrimaryForCustomer: false`, missing CustomerId stays
   absent). **Preserve `_id`, `TenantId`, audit fields** so the
   audit trail is intact and the document looks like it was always
   in the target collection.
3. **Verify**:
   ```js
   db.Contacts.find({ Email: "mitar@gmail.com" })
   // shape matches the new target schema?
   ```
4. **Then** drop the source collection.

The mistake is doing 4 before 2. Once the source is dropped, the
migration is theoretical.

## Index migration when fields move

When `Customer.Country` (flat string) becomes
`Customer.BillingAddress.Country` (nested):

```csharp
// IndexInitializer for the entity
foreach (var stale in new[] { "ix_customers_country" })
{
    try { await collection.Indexes.DropOneAsync(stale); }
    catch (MongoCommandException) { /* not present, fine */ }
}

await collection.Indexes.CreateOneAsync(new CreateIndexModel<Customer>(
    Builders<Customer>.IndexKeys.Ascending("BillingAddress.Country"),
    new CreateIndexOptions { Name = "ix_customers_billing_country" }));
```

Why the try/catch: on a fresh DB the stale index won't exist; we
don't want the initializer to crash on that. The catch swallows
`MongoCommandException` ("index not found") and lets the create run.

**Test this on a fresh DB** before merging. If the create-and-drop
sequence is wrong, you'll see it as an
`MongoCommandException: An existing index has the same name as the
requested index` on the next `migrate-database`. Add the offending
name to the drop list.

## Partial unique indexes — gotchas

When the partial filter expression of an existing index changes
(e.g. `WHERE IsPrimary=true` becomes
`WHERE IsPrimaryForCustomer=true`), Mongo refuses to update in place:
the create returns the "same name, different options" error.
**You must drop and recreate** even if the keys are identical.

The IBL360 ContactIndexInitializer renames v1→v2 to make this
explicit:
- `ux_contacts_tenant_customer_email` → `ux_contacts_tenant_customer_email_v2`
- `ux_contacts_tenant_customer_primary` → `ux_contacts_tenant_customer_primary_v2`

The v1 index is dropped at seed time; the v2 takes its place. Next
refactor will be v3.

## After every migration: the user MUST hard-refresh

The React i18n bundle is cached client-side after the first fetch.
New `Enum:*`, `Menu:*`, `Permission:*` keys you added during the
refactor won't render until the user hits Ctrl+F5. Tell them.
Otherwise they'll see raw keys ("Enum:PartyStatus.Active") in
the UI and assume the deploy broke.

The dynamic permission claims are also cached for the duration of
the session; new role grants need a logout/login or a hard refresh
to take effect for the currently-logged user. The Admin Console's
"Refresh" button does NOT do this for self.
