# Improvement

## Proposed Change

Centralize the file→project→namespace mapping in **one** place and make every
script and SKILL doc consume it, so the toolkit works on both templates.

1. **abp-core/scripts/abp_context.py** — new `resolve_artifact(ctx, kind, plural)`
   returning `(project_dir, dir, namespace)` per template for every artifact kind
   (`entity`, `enum`, `consts`, `error_codes`, `dto`, `appservice_interface`,
   `appservice_impl`, `repo_interface`, `repo_impl`, `data_context`, `permissions`,
   `mapper`, `data_seed`, `localization`). Plus helpers `layer_project_dir`,
   `test_project_dir`, `data_layer`, and a `--show-layout` CLI. New per-layer
   placeholders (`{{DOMAIN_PROJECT}}`, `{{DOMAIN_SHARED_PROJECT}}`,
   `{{APPLICATION_PROJECT}}`, `{{CONTRACTS_PROJECT}}`, `{{DATA_PROJECT}}`,
   `{{HTTPAPI_PROJECT}}`, `{{HOST_PROJECT}}`) collapse onto `{{PROJECT_ROOT}}` in
   nolayers, so one template string works on both.

2. **abp-feature-dev/scripts/scaffold_entity.py** — resolve every output path and
   namespace via `resolve_artifact`; split AppService interface (Contracts) from
   impl (Application) and repo interface (Domain) from impl (data project);
   `--output` now redirects the whole layer tree. Strip redundant self-`using`s
   (layered shares one flat namespace). Detect the real `*MongoDbContext` class
   name. Layered custom repository uses a Domain-safe primitive `filterText`
   signature instead of `Get{Plural}Input` (a Domain repo must not reference
   Application.Contracts); `--custom-repository auto` defaults to **no** in layered.

3. **abp-feature-dev/scripts/verify_feature.py** — resolve expected files/namespaces
   per template; build the whole solution when present (layered spans several
   projects).

4. **abp-mongodb/scripts/register_entity_in_context.py** — default entity/repo
   namespaces from `resolve_artifact`; skip self-`using`.

5. **abp-testing** — `scaffold_test.py` + `AppServiceTest.cs.tmpl` resolve test
   project (`*.MongoDB.Tests` on layered), base class (`{Project}MongoDbTestBase`)
   and `using`s per template via `{{TEST_USINGS}}` / `{{TEST_BASE_CLASS}}`.

6. **abp-module-architecture/scripts/analyze_module_ownership.py** — detect template
   and scan the layered layer projects; report grouped per concern.

7. **SKILL.md + references** across all 7 skills — document both templates with the
   nolayers↔layered mapping and point at `resolve_artifact` as the source of truth.

Also fixes a latent, template-independent bug found during evaluation: an `enum`
filter on a lifecycle-injected `Status` field emitted `public Status? Status`
(non-existent type); it now resolves to the declared enum (`ProductStatus`).

## Rationale

One mapping, two layouts: get `resolve_artifact` right once and seven skills
follow, instead of scattering `if template_type ==` branches. Correctness drivers:
in layered, `Application.Contracts` references `Domain.Shared` but not `Domain`, so
enums a DTO needs must live in `Domain.Shared`; and a `Domain` repository interface
must not depend on `Application.Contracts`.

## Scope

All ibl-abp skills + the shared `abp_context.py`. nolayers output is kept
byte-compatible with the previous behavior (no regression).

## Risks

Low. The nolayers branch reproduces the historical IBL360 layout exactly;
validated by compile + an A/B eval (see validation.md). The layered custom
repository intentionally drops per-field filters from the repo interface (they
stay in the AppService) — documented in the skill.
