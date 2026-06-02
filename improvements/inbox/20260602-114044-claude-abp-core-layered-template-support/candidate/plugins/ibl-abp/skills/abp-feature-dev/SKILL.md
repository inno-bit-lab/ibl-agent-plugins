---
name: abp-feature-dev
description: 'End-to-end ABP feature development with an interview-driven workflow. Use to add or port entities, create AppServices and DTOs, scaffold CRUD endpoints, design aggregates or DomainServices, configure permissions, mapping, filters, bulk delete, Excel export, lookup endpoints, concurrency stamps, soft delete, lifecycle methods, explicit test coverage decisions, and final validation. Trigger on "add an entity", "port this table", "new AppService", "scaffold CRUD", "add permissions", "aggregate root", "DTO", "Mapperly", "filtri di lista", "export Excel", or any ABP feature work.'
---

# ABP Feature Development

End-to-end workflow for **adding a feature to an ABP project**: interview the
user → design entity → propose filters → ask about optional platform features
→ scaffold → register in data context → wire permissions/mapping/localization →
validate.

This skill is the **orchestrator**. It delegates specific concerns to sibling
skills:

| Concern | Delegate to |
|---|---|
| Project conventions, base classes, anti-patterns | `abp-core` |
| Module ownership, Shared-vs-feature placement, modular migration | `abp-module-architecture` |
| MongoDB context, custom repositories, indexes | `abp-mongodb` |
| Making entity tenant-aware, tenant filter behavior | `abp-multitenancy` |
| React UI (CRUD page, route, sidebar entry, i18n) | `abp-react-ui` |
| Integration tests | `abp-testing` |

## When to read which reference

| Working on... | Read |
|---|---|
| Entity shape, aggregates, child entities, domain services | `references/ddd-patterns.md` |
| AppService, DTOs, validation, mapping, exceptions | `references/application-layer.md` |
| Permissions, `[Authorize]`, ownership checks, role vs permission | `references/authorization.md` |
| Optional features (bulk delete, Excel export, lookup, concurrency, soft delete) | `references/optional-features.md` |
| Lifecycle / state machine entities (Status field with allowed transitions) | `references/lifecycle-patterns.md` |
| Smart filters: what to propose given an entity's property types | `references/filter-design.md` |
| Granting new permissions to default roles via the tenant seed contributor | `references/data-seeding.md` |
| **Two or more entities sharing the same field set (Customer/Supplier, Lead/Customer)** | `references/business-party.md` |
| **Schema refactor with live data: migrating BSON documents during a backend change** | `references/data-migration.md` |

## The workflow — never skip the interview

A scaffolder that always emits the same shape produces bloated code for trivial
entities and undercooked code for rich ones. To get the right shape every time,
**run the interview before generating code**. The user can short-circuit any
question with "default" / "as you suggest" — but always *ask*.

### Module placement gate

Before Step 1, check whether the solution already has `modules/` or the user
mentions modularization, bounded contexts, Shared, CRM/HR/Finance, moving
resources, or "where should this entity live?" If yes, run
`abp-module-architecture` first and do not scaffold into the host until module
ownership is decided.

The chosen module controls:

- namespace root (`Ibl360Crm.*`, not `Ibl360.*`)
- permission group and permission names
- domain error code namespace
- localization resource
- MongoDB context and indexes
- React UI package/folder and menu registry
- seed/migration work for existing permission grants

The interview has six steps. Each builds on the previous one; gather
everything before you call the scaffolder so the generated code is right
on the first pass.

### Step 1 — Intake: entity shape

1. Confirm entity name (PascalCase singular) and plural (folder/collection name).
2. List the properties. If the user pasted a schema (Postgres `CREATE TABLE`,
   ER diagram, JSON Schema, screenshot), translate it to the property list
   yourself and show it back for confirmation — don't make the user re-type it.
3. For each property capture: name, .NET type, nullable, default value, max
   length / range (for validation).
4. Identify enums. If a string/text field has a `CHECK IN (...)` constraint or
   the user mentions a fixed set of values ("status: PROSPECT, ACTIVE,
   CHURNED"), propose extracting it to a C# enum and ask for confirmation.
   Suggested enum names: `{Entity}Status`, `{Entity}Segment`, `{Entity}Type`.

### Step 2 — Audit and persistence shape

Ask one short question, with default and brief rationale:

```
Audit level for {Entity}?
  - Entity            (no audit fields)        — rarely used
  - Audited           (Creation/LastModified) — default for most CRUD
  - FullAudited       (+ soft delete + deleter)   — recommended when:
                         records should not be hard-deleted (legal/audit)
                         OR there's a real chance of accidental deletes
[default: Audited]
```

If multi-tenancy is enabled in the project (check `IsMultiTenant` in the
project's `*Module.cs`), ask **two** related questions — keep them separate, they
control different things and the user often wants different answers.

**Q1 — Data scoping (does the entity carry a `TenantId`?):**

```
Is {Entity} tenant-scoped (each tenant has its own records)?
  - yes  → IMultiTenant + TenantId on the entity; data is isolated per tenant
  - no   → host-only or cross-tenant resource (no TenantId)
[default: yes if the project is multi-tenant and the source schema hints at it
 — e.g. comment says "del tenant", or rows are filtered by an org/account id]
```

**Q2 — Permission side (who in the admin UI can be granted these permissions?):**

This question is easy to get wrong and the failure mode is silent until
runtime. Always ask explicitly — don't infer from Q1.

```
Permission side for {Entity} (who can be granted these permissions?):
  - Tenant   → only tenant users see and can be granted these permissions.
               The host admin user CANNOT operate on this entity (HTTP 403).
               Use when only tenant-side actors should manage this data.
  - Host     → only host (cross-tenant) users; tenant users hidden.
               Use for cross-tenant admin tools, billing, infra.
  - Both     → permission grantable to host AND tenant users (the default if
               you don't pass a side). Use when this is shared functionality
               (e.g. read-only inspection by host support, but also tenant
               self-service).
[default: Both — it's the safe choice for a CRUD entity unless you have a
 specific reason to lock it down. Tenant-only is correct for tenant-private
 data IF the operating user will also be tenant-side; pick Both if the host
 admin will ever need to touch this entity for support, audit, or testing.]
```

A common gotcha: `IMultiTenant` on the entity (Q1=yes) does **NOT** imply
`MultiTenancySides.Tenant` on the permission (Q2=Tenant). The first controls
data isolation; the second controls who can be granted the permission. A
tenant-isolated entity with `Both` permission means the host admin can switch
into a tenant context (`__tenant` header) and operate on tenant data — useful
during dev / smoke tests / support workflows.

**Warning if you pick `Tenant`:** the default host admin seeded by ABP cannot
operate against the entity without a tenant context. To smoke-test from the
host you'll need to either (a) seed a tenant + tenant admin and log in as
that user, or (b) include the `__tenant: <name|id>` header on every request.
If the user wants a fast post-scaffold sanity check from the host admin
without tenant setup, suggest `Both` for now and tighten later.

Ask about concurrency stamp only if there's a real risk of concurrent edits
(many editors, long edit sessions, optimistic locking needed):

```
Add ConcurrencyStamp for optimistic locking? [default: no]
```

### Step 3 — Smart filter proposal

This is the **hallmark** of this skill: do not generate a blank `Filter`
text-box and a `PagedAndSortedResultRequestDto`. Analyze the properties you
just captured and propose a typed `Get{Entities}Input` with concrete filters.

**Propose, then let the user accept or extend.** See
`references/filter-design.md` for the full mapping table. The short version:

| Property type | Proposed filter | Notes |
|---|---|---|
| `string` (short/identifier) | `string? {Name}` exact-or-contains | choose based on length / meaning |
| `string` (long text / description) | `string? Filter` (free text across multiple) | typical name + display + tax_id |
| `enum` | `T? {Name}` nullable enum | |
| `bool` | `bool? {Name}` | |
| `DateTime[?]` | `DateTime? {Name}From`, `DateTime? {Name}To` | range |
| `int/long/decimal[?]` | `T? {Name}Min`, `T? {Name}Max` | range |
| `Guid` foreign key | `Guid? {Name}` exact | |

After proposing, render it back to the user:

```
Proposed filters for Customer list:
  - Filter      (text, searches LegalName + DisplayName + TaxId)
  - Status      (CustomerStatus?, enum)
  - Segment     (CustomerSegment?, enum)
  - Country     (string?, exact match, uppercase normalized)
  - CreatedFrom (DateTime?)
  - CreatedTo   (DateTime?)

Accept these, or want to add/remove any?
```

### Step 4 — Optional platform features (ASK before adding)

These features make the AppService much more useful in admin/back-office UIs.
They are NOT included by default — ask the user one at a time. If the user
says "give me everything", apply sensible defaults (the first four are
common, lookup is situational).

```
Optional endpoints to include? (yes/no for each)
  - Bulk delete         (DeleteByIdsAsync, DeleteAllAsync with filter)         [default: no]
  - Excel export        (GetListAsExcelFileAsync + download token cache)       [default: no]
  - Lookup endpoint     (GetLookupAsync — id + display, for dropdowns)         [default: no]
  - Custom repository   (typed filter methods in a dedicated repository)       [default: yes if >3 filters]
```

See `references/optional-features.md` for the full pattern of each (cache
keys, content type, route conventions).

### Step 5 — Lifecycle / state machine (only if applicable)

If you identified a `Status`-like enum in step 1, ask:

```
{Entity}.Status looks like a lifecycle. Define allowed transitions?
  - yes  → I'll generate a ChangeStatus method that validates transitions
  - no   → status is just a settable field
[default: yes if the enum name ends in "Status" or "State"]
```

If yes, ask for the allowed transitions:

```
From → To allowed transitions (terminal states have no outgoing arrows):
  Prospect → Active
  Active → Churned

Anything else allowed? (e.g. Active → Prospect for reactivation)
```

This generates a `ChangeStatus(newStatus, IClock)` method that:
- Validates the transition
- Updates a `StatusChangedAt` timestamp via `Clock.Now`
- Throws `BusinessException("{{ROOT_NAMESPACE}}:{Entity}s:InvalidStatusTransition")`
  with localized message

See `references/lifecycle-patterns.md` for the full pattern.

### Step 6 — Confirm before generating

Render a summary of all choices and ask the user to confirm:

```
About to generate Customer feature:
  Properties: LegalName (string, required), DisplayName (string, required),
              TaxId (string?, max 64), FiscalCode (string?, exactly 16 chars,
              uppercase), Address (string?, max 512), Country (string, 2 chars,
              default "IT"), Segment (CustomerSegment), StatusChangedAt (DateTime?)
  Enums:      CustomerStatus { Prospect, Active, Churned }   [BSON: string]
              CustomerSegment { Smb, Enterprise, Public }    [BSON: string]
  Audit:      Audited
  Data scope: IMultiTenant (yes — TenantId on entity)
  Perm side:  Both (host admin can switch tenant and operate) | Tenant | Host
  Concurrency:no
  Filters:    Filter (text), Status, Segment, Country
  Endpoints:  + ChangeStatusAsync (lifecycle)
              + no bulk, no excel, no lookup
  Repository: generic IRepository<Customer, Guid>

OK to proceed?
```

The user can edit any line — the cost of a wrong choice here is small, the
cost of regenerating after they spot it in code is much bigger.

## After the interview — execute

Once the interview is done, run the scaffolder with everything captured:

```bash
python <skills-root>/abp-feature-dev/scripts/scaffold_entity.py \
    --name Customer --plural Customers \
    --properties "LegalName:string,DisplayName:string,..." \
    --enums "CustomerStatus:Prospect,Active,Churned;CustomerSegment:Smb,Enterprise,Public" \
    --audit Audited \
    --multi-tenant yes \
    --filters "Filter:text(LegalName,DisplayName,TaxId);Status:enum;Segment:enum;Country:string" \
    --lifecycle "Status:Prospect->Active,Active->Churned" \
    --bulk-delete no --excel-export no --lookup no \
    --custom-repository no
```

See **"The scaffolder"** below for the full argument reference.

Then proceed through the **finalization steps** (see "Finalization" further
down): register in DbContext, add IMultiTenant if needed, merge permissions,
add mappers and localization, ask the explicit test coverage question, and run
final validation.

## The scaffolder

`scripts/scaffold_entity.py` produces the entity + DTOs + AppService + permission
snippet + (optional) custom repository + (optional) lifecycle method + (optional)
bulk/excel/lookup endpoints + Mapperly + localization snippets.

### Solution template — where files land

The scaffolder auto-detects the solution template (`abp_context.py`) and places
every file accordingly. **You don't choose paths or namespaces by hand** — the
file→project→namespace mapping lives in one place, `resolve_artifact()` in
`abp-core/scripts/abp_context.py`, and both the scaffolder and `verify_feature.py`
read from it. Two templates are supported:

- **nolayers** (single-project / Simple Monolith — the IBL360 layout): one
  project, layer expressed by folder + namespace segment
  (`Entities/`, `Services/`, `Services/Dtos/`, `Data/`).
- **layered** (DDD — IBLTermocasa and similar): separate projects
  (`*.Domain`, `*.Domain.Shared`, `*.Application`, `*.Application.Contracts`,
  `*.MongoDB`), with a **flat** `Root.Plural` namespace shared across the
  aggregate's files. Persistence code is `Root.MongoDB`, permissions `Root.Permissions`.

### File layout produced

**Single-project (nolayers):**

```
{{PROJECT_ROOT}}/Entities/{Plural}/        {Entity}.cs, {EnumName}.cs, (opt) {Entity}Manager.cs
{{PROJECT_ROOT}}/Services/Dtos/{Plural}/   {Entity}Dto, CreateUpdate{Entity}Dto, Get{Entities}Input,
                                           (opt) Change{Entity}StatusDto / {Entity}LookupDto / {Entity}ExcelDto
{{PROJECT_ROOT}}/Services/{Plural}/        I{Entity}AppService.cs, {Entity}AppService.cs
{{PROJECT_ROOT}}/Data/{Plural}/            (only --custom-repository yes) I{Entity}Repository, Mongo{Entity}Repository
{{PROJECT_ROOT}}/{{PROJECT_NAME}}DomainErrorCodes.cs   (only if lifecycle; merged if exists)
```

**Layered (DDD)** — same files, fanned out across projects (flat `Root.Plural` namespace):

```
{{DOMAIN_PROJECT}}/{Plural}/             {Entity}.cs, (opt) {Entity}Manager.cs, (opt) I{Entity}Repository.cs
{{DOMAIN_SHARED_PROJECT}}/{Plural}/      {EnumName}.cs   ← enums live here so Contracts can reference them
{{DOMAIN_SHARED_PROJECT}}/{{PROJECT_NAME}}DomainErrorCodes.cs   (only if lifecycle)
{{CONTRACTS_PROJECT}}/{Plural}/          {Entity}Dto, CreateUpdate{Entity}Dto, Get{Entities}Input,
                                         I{Entity}AppService.cs, (opt) Change/Lookup/Excel DTOs
{{APPLICATION_PROJECT}}/{Plural}/        {Entity}AppService.cs
{{DATA_PROJECT}}/MongoDb/{Plural}/       (only --custom-repository yes) Mongo{Entity}Repository.cs
```

> Why enums move to `Domain.Shared` in layered: `Application.Contracts` references
> `Domain.Shared` but **not** `Domain`. A DTO's enum property must therefore live in
> `Domain.Shared` or the contracts project won't compile. The entity (in `Domain`)
> still sees it because `Domain` also references `Domain.Shared`. In nolayers it's one
> project, so enums sit next to the entity.

> Custom repository in layered: the interface lives in `Domain` and must stay free of
> `Application.Contracts` types, so its layered variant takes a primitive `filterText`
> instead of `Get{Entities}Input`. Per-field filtering stays in the AppService (the
> ABP-idiomatic site). That's also why `--custom-repository auto` defaults to **no** in
> layered — pass `--custom-repository yes` to force it.

Review artifacts (`_permissions_snippet.txt`, `_mapper_snippet.txt`,
`_localization_snippet.json`, `_next_steps.md`) are always written under
`{Entity}'s folder`/`_review_artifacts/` for manual merge.

### Key arguments

```
--name Customer                  Entity name (PascalCase, singular)
--plural Customers               Folder/collection name (default: name + 's')
--properties "Name:Type[?]=Default,..."   See property syntax below
--enums "Name:V1,V2,V3;Name2:..."         Enum declarations (semicolon-separated)
--audit Entity|Audited|FullAudited        Default: Audited
--multi-tenant yes|no            Default: detect from project IsMultiTenant
--concurrency yes|no             Default: no
--filters "Spec"                 See filter syntax below
--lifecycle "Field:A->B,B->C"    State transitions (only for status-like enums)
--bulk-delete yes|no             Default: no
--excel-export yes|no            Default: no
--lookup yes|no                  Default: no (also pass --lookup-display Name)
--custom-repository yes|no       Default: yes if filter spec has >3 entries
--split-create-update yes|no     Default: no (CreateUpdateDto). yes → separate dtos
```

### Property syntax

```
Name:Type[?][=Default][@MaxLength|MinLength..MaxLength]
```

Examples:
- `Name:string` — string, required, no length cap
- `Description:string?@2000` — nullable string, max 2000 chars
- `Code:string@3..10` — required string, between 3 and 10 chars
- `Price:decimal=0` — required decimal, default 0
- `PublishedAt:DateTime?` — nullable date
- `Status:CustomerStatus=Prospect` — enum reference (must be in `--enums`)

### Filter syntax

```
FilterName:Kind[(ExtraArgs)]
```

Kinds:
- `text` — free-text contains; with `(F1,F2,F3)` it ORs across those fields
- `string` — exact match (case-insensitive)
- `enum` — nullable enum equality
- `bool` — nullable bool equality
- `dateRange:Field` — `{Field}From`, `{Field}To`
- `numRange:Field` — `{Field}Min`, `{Field}Max`
- `guid:Field` — exact Guid match

### Interactive mode

If you pass no arguments, the scaffolder runs the interview itself:

```bash
python <skills-root>/abp-feature-dev/scripts/scaffold_entity.py
```

Prefer the conversational interview led by Claude (steps 1–6 above): the
script's prompts are a fallback for when Claude is invoked directly via CLI.

## Finalization (after scaffolding)

The scaffolder writes code but several steps need orchestration. Don't
mark a feature "done" until all of these are completed.

1. **Register in data context.** Delegate to `abp-mongodb` (MongoDB) or apply
   the EF Core flow.

2. **Add IMultiTenant** if step 2 of the interview chose `yes`. Delegate to
   `abp-multitenancy`.

3. **Merge the permission snippet.** Read `_permissions_snippet.txt`, integrate
   the `Permissions` class block and the `PermissionDefinitionProvider`
   block manually into the project's existing files. Use
   `MultiTenancySides.Tenant` if the entity is multi-tenant.

4. **Grant the new permissions in the tenant data seed contributor.** Search
   the project for an `*TenantDataSeedContributor.cs` (or any contributor that
   grants permissions to roles via `IPermissionManager.SetForRoleAsync`). If
   one exists, add the new `{Entity}Permissions.Default/Create/Edit/Delete`
   to the admin role grants — see `references/data-seeding.md` for the
   pattern. **Skipping this is the #1 reason "I added the entity but the
   sidebar item doesn't appear"**: the React permission guard
   (`requiredPolicy: '{Module}.{Entity}'`) hides the menu entry, and the
   default admin user has no grant for the new permission until the seed
   runs again. After editing the contributor, run `migrate-database.ps1`
   (or `dotnet run --project {Host} -- --migrate-database`) to apply.
   If no seed contributor exists, surface this to the user: they must
   either grant the permission via Admin Console UI, or add a contributor
   now (the skill provides a template).

5. **Merge the mapper snippet.** Read `_mapper_snippet.txt`, append the
   Mapperly mapper(s) into the project's central `*Mappers.cs` partial — in
   layered that's `{{PROJECT_NAME}}ApplicationMappers.cs` in the Application
   project; in single-project it's `ObjectMapping/{{PROJECT_NAME}}Mappers.cs`.
   If the project uses AutoMapper, use the AutoMapper variant in the snippet
   instead.

6. **Merge localization keys.** Read `_localization_snippet.json`, integrate
   into every project language file (typically `it.json`, `en.json`, etc.).
   The snippet covers UI labels, enum values, permission labels, and
   business-exception messages (if lifecycle).

   **Critical**: after the backend serves the new keys, the React client
   has them cached from the previous boot. The user MUST hard-refresh
   (Ctrl+F5) so the i18n layer re-fetches `/api/abp/application-localization`
   and merges the new bundle. Without a refresh, new `Enum:*`, `Menu:*`,
   `Permission:*`, and BusinessException keys render as raw key strings
   (e.g. "Enum:AccountType.Bank" instead of "Bancario"). Always mention
   this step when handing the feature off to the user.

7. **Propose the React UI.** If the solution contains a React app
   (`react/` or `react-public-web/` with `@tanstack/react-router` in
   `package.json`), the feature isn't really done until users can interact
   with it. Ask:

   ```
   You have an AppService for {Entity}. Want me to add the React UI now?
     - yes → typed API client + CRUD page + route + sidebar entry + i18n keys
     - no  → backend only; the API is consumable at /api/app/{entity-kebab}
   [default: yes — defer only when explicitly building a backend-first integration]
   ```

   If yes, delegate to `abp-react-ui`. **Heads-up for `abp-react-ui`**:
   if you scaffolded a complex entity (≥10 fields, embedded VOs, lists),
   the right pattern is a dedicated `/{plural}/new` + `/{plural}/:id/edit`
   page with tabs — NOT the inline dialog. The list page navigates to it
   on row-click and on "New". `abp-react-ui/references/complex-edit-page.md`
   has the full template; the rule of thumb lives in its Step 4.

   If the project has no React app, skip silently.

8. **For complex UI, run `impeccable` after scaffolding.** When the
   entity took the dedicated edit-page path, `abp-react-ui` Step 7
   invokes `impeccable` as a polish pass to catch responsive bugs
   (grid-explodes-on-mobile), tap-target sizes, sticky chrome, nested
   cards, a11y. Don't skip — multi-tab forms have many more places to
   break than dialogs.

9. **Ask for test coverage.** Do not silently skip this step. If the user
   already explicitly requested or rejected tests, honor that. Otherwise ask:

   ```text
   Do you want tests for {Entity}?
     - backend   -> ABP integration tests for AppService/domain behavior
     - frontend  -> React/Vitest tests for the CRUD page
     - both      -> backend + frontend tests
     - none      -> skip tests; final handoff will mention this gap
   [default: backend for backend-only features; both when React UI was generated
    and the frontend test setup is healthy]
   ```

   If backend or both: delegate to `abp-testing` and create/update
   `{TestProject}/{Plural}/{Entity}AppService_Tests.cs`.

   If frontend or both: delegate to `abp-react-ui` and create/update
   `react/src/pages/{plural}/{Entity}Page.test.tsx` or the equivalent tests
   for dedicated create/edit pages.

   If tests cannot be added because the existing setup is broken, report the
   pre-existing failure and ask whether to add only the unaffected side. If the
   user chooses `none`, the final handoff must say this was an explicit skip.

10. **Run final validation.** This is mandatory — see "Validation" below.
    Run validation after the selected tests have been generated or explicitly
    skipped.

11. **Final handoff.** Include the selected test scope, test files added or
    updated, test commands run, and any skipped coverage with the reason.

## Validation

After scaffolding and finalization, **always** run the validation script
before declaring the feature complete:

```bash
python <skills-root>/abp-feature-dev/scripts/verify_feature.py --entity Customer
```

It checks:
- All expected files exist with the right namespaces
- DbContext has the new `IMongoCollection<>` and `modelBuilder.Entity<>` block
- `{Module}Permissions.{Plural}` constants exist and are wired in the provider
- The Mapperly mapper class is present in the central mapper file
- Localization keys exist in all language files (warns on missing translations)
- Optional: `dotnet build` succeeds. It builds the whole solution when a
  solution file is present (so a layered solution's Domain / Application /
  MongoDB projects are all covered), falling back to the single project
  otherwise. Pass `--no-build` to skip.

If backend tests were selected, also run:

```bash
dotnet test --filter {Entity}AppService_Tests
```

If frontend tests were selected, run the project's equivalent targeted command,
for example:

```bash
npm run test:run -- {Entity}Page.test.tsx
```

If a broader frontend build/test command fails because of pre-existing
unrelated errors, identify the unrelated files and still report whether the new
tests compile/run when possible.

A clean exit means the feature is wired correctly end-to-end. Any failure
gives a precise pointer (file + line + missing piece) — fix it before
moving on.

### Build flags gotcha (Windows)

`dotnet build -p:UseAppHost=false -t:Compile` is the right flag set for
**validation** during scaffolding because the running backend holds a lock
on `apphost.exe`. But it has a side effect: **no `Ibl360.exe` is produced**.
If you then try to `dotnet run --project Ibl360 --no-build` to apply a
migration or restart the host, it fails with "Impossibile trovare il file
specificato" pointing at `bin/Debug/net*/Ibl360.exe`.

The order that works in practice when you need both validate-and-run:

1. **Stop the running backend first** (it's the one holding the apphost lock).
2. Run a **plain** `dotnet build` (no `-t:Compile`, no `UseAppHost=false`) —
   this regenerates `apphost.exe`.
3. Then `dotnet run --project {Host} --no-build -- --migrate-database`.
4. Then `dotnet run --project {Host} --no-build` in the background to
   restart the API.

If you only need to validate that the code compiles (no run), stick with
`-p:UseAppHost=false -t:Compile` — it's faster and survives a running host.

## When to skip the scaffolder

The scaffolder produces a good default but is **not the right tool when**:

- **Modifying an existing entity.** The scaffolder always wants a fresh
  folder. For modifications, edit by hand — see "Modifying an existing
  feature" below.
- **Deleting an entity.** Likewise — see "Removing a feature" below.
- **The entity is a child entity** (owned by another aggregate root —
  `OrderLine` under `Order`). Child entities don't get their own repository
  or AppService; embed them in the aggregate root and expose methods on it.
- **The use case is heavily custom** (no CRUD shape: bulk import, event
  replay, computed aggregates). Generate just the entity and write the
  AppService by hand.
- **The user is porting an existing entity** and explicitly wants only the
  domain model. Skip the AppService generation with `--no-app-service`.

## Modifying an existing feature (no scripts)

The scaffolder is for the "blank page" case. Modifications are always
done by hand because the right answer depends on what already exists and
what else depends on the part you're changing. Claude does the grep
itself.

### General workflow

1. **Identify the change.** Examples: rename a property, add a filter,
   change permission policy, add a lifecycle transition, swap enum for
   string, replace AutoMapper with Mapperly, split CreateUpdateDto into
   separate CreateDto + UpdateDto.

2. **Build the impact map.** Grep both backend and frontend for the
   thing you're changing. For a property rename `Foo` → `Bar`:

   - Backend: entity, DTOs (input/output/filter), AppService (`ApplyFilters`,
     `CreateAsync`, `UpdateAsync` mapping), mapper, integration tests,
     `Localization/*.json` field label keys
   - Frontend (if applicable): `lib/api/{entity}.ts` (DTO type, filter
     type, query params), page (column header, table cell, Zod schema,
     form `<Field>`, `openEdit` reset, `onSubmit` mapping), locale `.json`

3. **Walk each file. Make the targeted change.** Don't drive-by refactor
   unrelated code in the same files.

4. **Surface data migrations.** Renaming a Mongo field doesn't rewrite
   existing documents. The user must decide: write an `updateMany`,
   leave the field with old name read-only, or accept data discontinuity.
   Never run the migration silently.

5. **Verify.**

   - `dotnet build -p:UseAppHost=false -t:Compile` on the .NET side
   - `npx tsc --noEmit -p tsconfig.app.json` on the React side
   - Re-run `verify_feature.py --entity {Entity}` for the structural checks

For the per-change impact maps, see **`references/modify-delete.md`** —
covers add filter, add column, add form field, rename property, rename
enum value, add lifecycle transition, change permission policy.

## Removing a feature (no scripts)

Removing in the wrong order leaves intermediate broken states (build
failures, dangling controller, broken admin UI). Order matters.

### Backend side

Walk this list. Delete each item only after the previous one is done,
so the build catches anything you missed.

> The folder paths below use the single-project (nolayers) layout. In a
> **layered** solution the same files live in their respective projects — entity
> in `*.Domain/{Plural}/`, DTOs + AppService interface in
> `*.Application.Contracts/{Plural}/`, AppService impl in `*.Application/{Plural}/`,
> enums + error codes in `*.Domain.Shared/`, custom repo impl in `*.MongoDB/`.
> See the "File layout produced" table above for the full mapping.

1. **`Localization/{ResourceName}/*.json`** — remove `Permission:{Plural}*`,
   `Menu:{Plural}`, `{Plural}`, `{Entity}`, `New{Entity}`, field labels not
   shared with other entities, enum value keys for any enum only this
   feature used, lifecycle error codes (`{Ns}:{Plural}:*`). Removing
   strings first is safest — nothing fails to compile from a missing key.

2. **Permission constants & provider entry**
   (`Permissions/*Permissions.cs` + `*PermissionDefinitionProvider.cs`).
   Removing them makes any `[Authorize({Plural}.Default)]` not compile —
   forcing you to face the next step.

3. **AppService + interface** (`Services/{Plural}/`).

4. **DTOs** (`Services/Dtos/{Plural}/`).

5. **Mapperly mapper** (the `Mapper<{Entity}, {Entity}Dto>` block in the
   central `*Mappers.cs`). Forgetting this leaves an orphan partial
   class that the source generator complains about.

6. **Custom repository** (if any, in `Data/{Plural}/`).

7. **Index initializer** (if any, in `Data/{Entity}IndexInitializer.cs`).

8. **DbContext registration** (`Data/*MongoDbContext.cs`) — remove
   `IMongoCollection<{Entity}>` line + `modelBuilder.Entity<{Entity}>(...)`
   block.

9. **Entity + enums** (`Entities/{Plural}/`).

10. **`*DomainErrorCodes.cs`** — remove the `{Plural}` nested class if
    the entity had a lifecycle.

11. **Tests** (`*ApplicationTests.cs` for the entity).

12. **`dotnet build -p:UseAppHost=false -t:Compile`** — confirms no
    references survive.

13. **MongoDB collection** — **don't drop automatically**. Surface to
    the user: "The Mongo collection `{Plural}` still contains data. Run
    `db.{Plural}.drop()` manually if you want a clean slate."

14. **Existing role permission grants** — orphan rows in the
    `IdentityRoleClaim` collection. Harmless but ugly. Flag for cleanup.

15. **`migrate-database.ps1`** — refresh the seed so the admin UI's
    permission tree no longer shows the deleted permissions.

### Frontend side

Delegate to `abp-react-ui` "Removing a feature". The backend delete
above doesn't touch the React app — and removing only the React side
leaves the API still serving requests. Always be explicit about which
side(s) the user wants removed.

For the complete delete checklist with impact maps, see
**`references/modify-delete.md`**.

## A worked example (the IBL360 Customer port)

Input from the user: a Postgres screenshot showing:
```
table customers — Clienti del tenant (BC crm)
columns: id uuid, legal_name text, display_name text, tax_id text NULL,
         fiscal_code char(16) NULL, address text NULL, country char(2) [IT],
         segment text CHECK IN (SMB,ENTERPRISE,PUBLIC),
         status text [PROSPECT] CHECK IN (PROSPECT,ACTIVE,CHURNED),
         created_at timestamptz [now()], status_changed_at timestamptz NULL
indices: PRIMARY id, UNIQUE tax_id WHERE NOT NULL, INDEX status/segment/country
lifecycle: PROSPECT -> ACTIVE -> CHURNED
```

The interview captures:
- Properties (translated from Postgres types to C#)
- Two enums: `CustomerSegment`, `CustomerStatus` — stored as **string** in BSON
  (see `abp-mongodb` "Storing enums as strings"), with name-based
  localization keys (`Enum:CustomerStatus.Prospect`, not `.0`)
- `Audited` (no soft delete), data scope multi-tenant yes (comment says "del tenant")
- **Permission side**: pick `Both` if the host admin will smoke-test or do
  support work without setting up a tenant. Pick `Tenant` only if you've
  already seeded a tenant + tenant admin and the host admin is intentionally
  locked out of this data. The default is `Both` because the cost of
  switching to `Tenant` later is one provider edit, while the cost of
  hitting 403 during a demo is much higher.
- Filters proposed: `Filter` (text across LegalName/DisplayName/TaxId),
  `Status` enum, `Segment` enum, `Country` string
- Lifecycle: Prospect → Active, Active → Churned
- No bulk, no excel, no lookup (the user is doing a CRUD port for an admin React UI)
- No custom repository (only four filters, generic repo is fine)
- Indexes: NOT created automatically — flag to the user (see
  `abp-mongodb` for the `IDataSeedContributor` pattern, the recommended one)

That's it — the CRUD endpoints become available at
`/api/app/customer/...` (auto-generated by ABP from the AppService), plus
`POST /api/app/customer/{id}/change-status` from the lifecycle method.

## When the user pushes back on private setters

The scaffolder produces entities with `private set` and a primary
constructor. If the user's project clearly prefers public setters
everywhere — check existing entities in the solution before assuming —
you have three options:

1. Leave the scaffold as-is and explain *why* it's stricter (invariants,
   testability). Most teams are happy once they see it.
2. Pass `--public-setters` (the scaffolder flips them).
3. For genuinely trivial CRUD entities, this is fine.

ABP's own guidance explicitly allows public setters *"for trivial CRUD"*
(true on both the single-layer and layered templates), but encapsulate the
moment a business rule appears.

## Hard-won lessons (read once, internalize forever)

These cost real sessions to learn. They are NOT in the basic scaffold
output; they are added on top by experience.

1. **The order that works for a schema-changing refactor**: stop
   backend → build with apphost → `--migrate-database` → restart.
   Skipping the build means `dotnet run --no-build` can't find
   `apphost.exe`. Skipping the migrate means new permission grants
   / new indexes don't exist. Skipping the restart means the
   `PermissionDefinitionProvider` cached in memory doesn't know
   about new permissions. See `references/data-migration.md`.

2. **The user has to hard-refresh** (Ctrl+F5) after any change to
   localization keys. The React i18n bundle is cached in memory after
   the first fetch — new `Enum:*`, `Menu:*`, `Permission:*` keys
   render as raw keys until invalidated. The dynamic permission
   claims are similarly cached for the current session; new role
   grants need logout/login (or refresh on the next request).

3. **Grants in the seed contributor are easy to forget** and the
   feedback is silent. Sidebar entry not showing → the menu's
   `requiredPolicy` guard hides it because the user wasn't granted.
   See `references/data-seeding.md`. Also: deleting an entity means
   deleting its grants from the seed AND from the DB
   (`AbpPermissionGrants`) — otherwise the next migrate re-creates
   them.

4. **Two entities sharing the same field set deserve an abstract
   base.** Customer / Supplier in IBL360 share ~95% of their fields;
   they extend a `BusinessParty` abstract aggregate. The pattern
   pays off ONLY when the lifecycle is also shared and the
   differences are small. See `references/business-party.md`.

5. **A list of VOs with a "default" needs the pointer on the
   parent**, not a flag on each VO. The flag-on-each-VO approach
   needs constant invariant maintenance ("only one default"); the
   pointer-on-parent approach makes it impossible to have two.

6. **Closed sets → enum.** If a string field has 5–15 possible
   values, model it as a C# enum. The React side will give it
   icons, the BSON store gets validated, and the data stays
   consistent. Free strings drift ("LinkedIn" vs "Linked-In" vs "li").

7. **Complex entity → dedicated edit page, not dialog.** When the
   form has tabs, value objects, or lists, the dialog is the wrong
   shape. `abp-react-ui` has the decision matrix in Step 4 and the
   template in `complex-edit-page.md`. Run `impeccable` after
   scaffolding — multi-tab forms break in more places than dialogs.

8. **Reusable UI components live in a shared folder**
   (`react/src/components/business-party/` for IBL360). Once two
   entities want the same address editor, the same socials editor,
   the same custom-fields editor, extract them. Concrete pages
   stay concrete; field-group components are shared.

9. **Removing an enum value or moving a field is a data migration,
   not just a code refactor.** Build green + restart green does NOT
   mean done. The BSON deserializer crashes at first read against
   any legacy document with the removed value, returning HTTP 500
   with a `FormatException`. The bug is invisible until someone
   reads the list. Mandatory sweep checklist in
   `references/data-migration.md` — run it BEFORE declaring the
   refactor complete, not after the first bug report.
