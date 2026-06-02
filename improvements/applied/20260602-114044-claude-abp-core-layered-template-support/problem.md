# Problem

## Affected Skill

- Plugin: ibl-abp
- Skills: abp-core, abp-feature-dev, abp-mongodb, abp-testing, abp-module-architecture, abp-multitenancy, abp-react-ui
- Agent/Host: claude

## What Happened

The ibl-abp skills assumed the **single-project (`nolayers`) ABP template** (the
IBL360 layout). Run against a **layered (DDD)** solution — separate `*.Domain`,
`*.Domain.Shared`, `*.Application`, `*.Application.Contracts`, `*.MongoDB`
projects (e.g. the IBLTermocasa porting project) — they produced structurally
wrong output:

- `scaffold_entity.py` wrote the entity, DTOs, AppService and custom repository
  into a **single** project under `Entities/`, `Services/`, `Services/Dtos/`,
  `Data/` folders, with namespaces `Root.Entities.{Plural}`,
  `Root.Services.{Plural}`, `Root.Services.Dtos.{Plural}`, `Root.Data.{Plural}`.
  In a layered solution these belong to **different physical projects** with a
  **flat** `Root.{Plural}` namespace, so the generated code does not match the
  solution and does not compile in place.
- `verify_feature.py` looked for the files at the nolayers paths/namespaces and
  would flag a correctly-placed layered feature as missing/mismatched.
- `register_entity_in_context.py` defaulted the entity namespace to
  `Root.Entities.{Plural}`, so the `using` it injected into the MongoDbContext
  was wrong on layered (the entity is actually `Root.{Plural}`), breaking the
  build.
- `scaffold_test.py` / `AppServiceTest.cs.tmpl` emitted nolayers `using`s and the
  `{Project}ApplicationTestBase` base; layered AppService integration tests must
  live in `*.MongoDB.Tests` with a provider-backed base and a single flat
  `using Root.{Plural};`.
- `analyze_module_ownership.py` only scanned `Entities/`, `Services/`,
  `Permissions/`, `Data/` folders, so it found nothing in a layered solution.

The skill metadata already detected `template_type` (`nolayers` / `layered` /
`microservice`), but only ever exposed a single `{{PROJECT_ROOT}}`, so nothing
downstream could place files per layer.

## Expected Behavior

Detect the solution template and place every generated/expected artifact in the
correct project and namespace for **both** layered and nolayers, without
regressing the existing single-project output.

## Evidence

- `scaffold_entity.py` hardcoded, e.g. `entities_ns = f"{root_ns}.Entities.{plural}"`,
  `entities_dir = project_dir / "Entities" / plural` (same for Services/Dtos/Data),
  all under one `project_dir`. Its header literally stated "laid out to match the
  IBL360 single-project ABP template".
- `abp_context.py` exposed only `PROJECT_ROOT`; no per-layer resolution.
- `verify_feature.py` expected `Entities/{plural}/{Entity}.cs` and namespace
  `Root.Entities.{plural}`.
- Verified real layered conventions in IBLTermocasa: entity in
  `src/IBLTermocasa.Domain/AppUsers/AppUser.cs` with `namespace IBLTermocasa.AppUsers;`
  (flat), DTO in `src/IBLTermocasa.Application.Contracts/AppUsers/`, MongoDbContext
  `namespace IBLTermocasa.MongoDB;`, permissions `namespace IBLTermocasa.Permissions;`.
