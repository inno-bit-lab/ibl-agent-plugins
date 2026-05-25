---
name: abp-module-architecture
description: 'Use when an ABP project is or should become modular: deciding entity/module ownership, proposing Shared or bounded-context modules, moving backend/React/localization/permissions between modules, or diagnosing missing menu/styles/permissions after modularization.'
---

# ABP Module Architecture

Use this skill before adding, moving, or splitting ABP features in a modular
solution. The goal is to keep bounded contexts coherent across backend,
MongoDB, permissions, localization, tests, and React UI.

## First Decision

Before writing files, answer one question:

> Which module owns this concept, and what other modules are allowed to know
> about it?

If the answer is unclear, stop and classify the entity using
`references/entity-ownership.md`. Do not place everything in the host just
because it is technically easy.

## Workflow

1. **Inventory current ownership**
   - Run `scripts/analyze_module_ownership.py` from the solution root when
     moving an existing project.
   - List backend entities/services/DTOs, permissions, localization keys, and
     React pages/API/components by host vs module.
2. **Choose module placement**
   - Domain-specific concepts go to a bounded-context module (`Crm`, `Hr`,
     `Finance`, etc.).
   - Cross-module primitives go to `Shared` only when two or more modules
     genuinely reuse them.
   - Host keeps composition, authentication, tenant bootstrap, app shell, and
     cross-cutting infrastructure.
3. **Plan the full resource move**
   - Backend contracts, domain/application code, Mongo context/indexes,
     permissions, error codes, localization, tests, and React UI move together.
   - Read `references/module-migration-checklist.md` before editing.
4. **Validate runtime behavior**
   - Build backend and frontend.
   - Run tests.
   - Check tenant-side permission grants after permission namespace changes.
   - Open the React app through the configured CORS origin, usually
     `http://localhost:5173`, not `http://127.0.0.1:5173`.

## Module Creation Heuristics

Propose a new module when one of these is true:

- A feature has its own aggregate roots, permissions, localization, and UI
  area.
- Two or more future entities clearly belong to the same business capability.
- The host module is gaining domain folders unrelated to composition.
- A feature would force unrelated modules to import a large implementation
  assembly instead of a small contract/shared dependency.

Do not create a module for a single helper, one DTO, or a component that is
only reused inside one bounded context.

## Delegation

| Work | Delegate |
|---|---|
| ABP base classes, DI, exception conventions | `abp-core` |
| Entity/AppService/DTO design inside the chosen module | `abp-feature-dev` |
| Mongo context, collection names, repositories, indexes | `abp-mongodb` |
| Tenant scoping and permission side | `abp-multitenancy` |
| Module-local or shared React UI | `abp-react-ui` |
| Integration tests after module moves | `abp-testing` |

## Common Failure Modes

- **Menu disappeared after modularization:** the React menu likely requires
  `NewModule.*` permissions but the tenant role still has old `HostModule.*`
  grants. Run the data seed/migrator and verify grants in the permission store.
- **UI lost styling:** Tailwind only scans `react/src`; add module React
  folders with `@source "../../../modules/<module>/react/src";`.
- **CORS errors only in browser:** frontend was opened with `127.0.0.1` while
  ABP CORS allows `localhost`. Use the configured `App:ReactUrl` origin or add
  the extra origin deliberately.
- **Backend compiles but endpoints missing:** module AppServices were moved but
  conventional controllers or `AddApplicationPartIfNotExists` were not wired in
  the module.
- **Old localizations still win:** localization keys were copied into the new
  resource but not removed from the host resource, or exception code namespace
  mapping still points to the host resource.
