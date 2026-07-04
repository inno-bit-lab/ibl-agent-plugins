# Verified analysis — DbMigrator loads custom-module Contracts

Self-contained excerpt for the DbMigrator seed/permission gap (part of the
"gap ibl-abp" candidate; the scaffold/permission sub-parts were verified ALREADY
FIXED upstream in PR #5 and are out of scope here).

## Summary

When a custom ABP module owns its seed contributor / permission definitions, the
standalone `*.DbMigrator` console app must `DependsOn` that module, or its
Contracts are not loaded and its seeds/grants never run — menus stay hidden.

## Evidence

- `Termocasa-react 1a1d1d4b` — "il DbMigrator non carica i moduli custom" → commit
  "fix(seed): DbMigrator carica i Contracts dei moduli custom"; the mongosh seed
  verification was rewritten by hand 4-5 times in the same session.

## Repo check at capture time

- `grep` over `plugins/`: ZERO occurrences of "DbMigrator". The existing
  `module-migration-checklist.md` says "run the migrator/seeder" but never states
  the DbMigrator project must depend on the custom modules. Gap confirmed real.

## Caveats for the processor

- Keep it a checklist/reference addition, not a script: the DbMigrator project
  name and module names vary per solution (resolved by `abp_context`) — use the
  parameterized placeholder `<CustomModule>Module`.

Source: reflection over `~/.claude` session transcripts. Session ids are opaque; no secrets present.
