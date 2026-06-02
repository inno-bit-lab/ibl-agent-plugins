# Validation

## Checks Run

- [x] All modified Python scripts compile (`py_compile`)
- [x] Resolver matches the real layered solution (IBLTermocasa) for all 16 artifact kinds
- [x] nolayers fixture reproduces the historical IBL360 layout (no regression)
- [x] Generated **layered** C# compiles (`dotnet build`, 0 errors)
- [x] A/B eval: layered-aware skill vs pre-change skill
- [x] Regression evidence added (latent enum-filter bug fixed)

## Commands

```bash
# 1. Syntax — all modified scripts compile
python -m py_compile \
  plugins/ibl-abp/skills/abp-core/scripts/abp_context.py \
  plugins/ibl-abp/skills/abp-core/scripts/validate_module.py \
  plugins/ibl-abp/skills/abp-feature-dev/scripts/scaffold_entity.py \
  plugins/ibl-abp/skills/abp-feature-dev/scripts/verify_feature.py \
  plugins/ibl-abp/skills/abp-testing/scripts/scaffold_test.py \
  plugins/ibl-abp/skills/abp-module-architecture/scripts/analyze_module_ownership.py \
  plugins/ibl-abp/skills/abp-mongodb/scripts/register_entity_in_context.py

# 2. Resolver vs the real layered solution + a nolayers fixture
python plugins/ibl-abp/skills/abp-core/scripts/abp_context.py --cwd <IBLTermocasa> --show-layout AppUsers
python plugins/ibl-abp/skills/abp-core/scripts/abp_context.py --cwd <nolayers-fixture> --show-layout Books

# 3. Compiler proof: scaffold a layered entity into the real solution, build, clean up
python .../scaffold_entity.py --cwd <IBLTermocasa> --name Gadget --plural Gadgets \
  --properties "Name:string@128,Code:string?@32,Kind:GadgetKind" --enums "GadgetKind:Basic,Premium" --no-app-service
dotnet build <IBLTermocasa>/src/IBLTermocasa.Domain/IBLTermocasa.Domain.csproj
dotnet build <IBLTermocasa>/src/IBLTermocasa.Application.Contracts/IBLTermocasa.Application.Contracts.csproj
```

## Result

**Pass.**

- **Resolver** — Output for IBLTermocasa matched the real files exactly across all
  16 artifact kinds (entity → `src/IBLTermocasa.Domain/{Plural}`, enum →
  `Domain.Shared`, DTO/interface → `Application.Contracts/{Plural}`, impl →
  `Application/{Plural}`, context → `MongoDB/MongoDb`, flat `IBLTermocasa.{Plural}`
  namespaces; persistence `IBLTermocasa.MongoDB`, permissions `IBLTermocasa.Permissions`).
  The nolayers fixture reproduced the historical `Entities/`, `Services/Dtos/`,
  `Services/`, `Data/` layout with `Root.Entities.*` / `Root.Services.*` namespaces.

- **Compile** — A layered entity + enum + DTOs generated into the real solution
  built with **0 errors** (`dotnet build` of `*.Domain` and `*.Application.Contracts`),
  proving the flat-namespace cross-project references resolve. Generated files were
  removed afterwards.

- **A/B eval** (abp-feature-dev, two layered prompts — a Postgres port and a new
  filtered entity — run with the new skill vs the pre-change snapshot):
  - New (layered-aware): **11/11 assertions (100%)** — files land in the correct
    layer projects with flat namespaces.
  - Old (pre-change): **0/11 (0%)** — nolayers folders + `.Entities.`/`.Services.`
    namespaces, wrong for a layered solution.
  - The new skill was also faster (≈79s vs ≈116s mean per run).

- **Bug fixed during eval** — an `enum` filter on a lifecycle-injected `Status`
  field emitted `public Status? Status` (non-compilable); now resolves to the
  declared enum, e.g. `public ProductStatus? Status`. Re-verified by regeneration.

- `register_entity_in_context.py` injected the correct flat `using IBLTermocasa.{Plural}`
  + collection + `modelBuilder.Entity<>` on a copy of the real context; `scaffold_test.py`
  emitted the `*.MongoDB.Tests` base + single flat `using` on layered and the
  three-using `{Project}ApplicationTestBase` shape on nolayers;
  `analyze_module_ownership.py` detected `layered` and inventoried the layer projects.

`validate_module.py`, `add_multitenant_to_entity.py` and `verify_enum_string_setup.py`
were already template-agnostic and were left unchanged.
