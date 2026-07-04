# Problem

## Affected Skill

- Skill: abp-module-architecture
- Plugin: ibl-abp
- Agent/Host: claude (observed); the issue itself is host-agnostic

## What Happened

When a custom ABP module owns its own data-seed contributor and permission
definitions, the standalone `*.DbMigrator` console app must declare
`[DependsOn(typeof(<CustomModule>Module))]` — otherwise it does not load the
module's Contracts, and the module's seeds and permission grants never run. The
migration/seed silently does nothing for that module: menus stay hidden because
the permissions were never granted.

The skill's `references/module-migration-checklist.md` tells the agent to "run
the migrator/seeder after the move" and to verify grants, but never says the
DbMigrator project itself must depend on the custom module. `grep` confirms
**zero** occurrences of "DbMigrator" in the repo today.

## Expected Behavior

- The module-migration guidance states that the `*.DbMigrator` project must
  `DependsOn` every custom module whose seed/permission definitions must run,
  with a verification step (did the seeds run? are the permissions in the store?).

## Evidence

- `Termocasa-react 1a1d1d4b` — "il DbMigrator non carica i moduli custom" →
  commit "fix(seed): DbMigrator carica i Contracts dei moduli custom"; the
  mongosh seed verification was rewritten by hand 4-5 times in the same session.
- Full verified analysis: `reflection-notes.md` candidate #7 (DbMigrator part).
