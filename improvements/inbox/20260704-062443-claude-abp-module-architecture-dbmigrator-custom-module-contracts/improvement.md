# Improvement

## Proposed Change

1. Extend `references/module-migration-checklist.md`, section "3. Permission
   Migration": add that the standalone `*.DbMigrator` console project must
   declare `[DependsOn(typeof(<CustomModule>Module))]` for every custom module
   whose `IDataSeedContributor` or `PermissionDefinitionProvider` must run —
   otherwise its Contracts are not loaded and its seeds/grants never execute.

2. Add a verification bullet: after `migrate-database`, confirm the module's
   seeds actually ran and its permissions exist in the store (not just "run the
   seeder").

3. Optionally add a matching entry to `SKILL.md` "Common Failure Modes":
   "Seeds/permissions of a custom module never applied → the DbMigrator project
   does not `DependsOn` that module."

## Rationale

Host-agnostic ABP domain knowledge (prose), no runtime/tool dependency. Closes a
real seed-time gap that produced hidden menus and hand-rewritten verification.

## Scope

- In: the DbMigrator ⇒ custom-module dependency rule + verification, in the
  module-migration checklist (and optionally the SKILL.md failure list).
- Out: the mongosh seed-verification helper itself (covered by the abp-mongodb
  local-vs-remote-topology artifact).

## Risks

- Keep it a checklist/reference addition, not a script — the exact DbMigrator
  project name and module names vary per solution and are resolved by
  `abp_context`, so the guidance must stay parameterized (`<CustomModule>Module`).
