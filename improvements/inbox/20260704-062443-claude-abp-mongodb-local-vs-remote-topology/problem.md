# Problem

## Affected Skill

- Skill: abp-mongodb
- Plugin: ibl-abp
- Agent/Host: claude (observed); the issue itself is host-agnostic

## What Happened

`abp-mongodb` covers contexts, repositories, indexes, enum representation, and
data migrations, but has **no guidance on which database is authoritative** when
a project has both a stale local Mongo and a current remote (Atlas). This caused
a real, high-severity failure: a multi-agent audit produced **3 HIGH findings
that were all false** because the agents counted documents on the stale local
`tcp-app-db` (705 docs) instead of the current Atlas database (590). The
connection env var (`TCP_REACT_MONGO_CONNECTION_STRING`) was absent from the
environment, so nothing pinned the audit to the right target.

Separately, mongosh parity / seed / cleanup queries are rewritten by hand 3-5
times per session because there is no reusable helper. `grep` confirms **zero**
occurrences of `mongosh` and no source-of-truth / `db.getName` / read-only
guidance in the skill today.

## Expected Behavior

- Before any audit, migration, or count, the skill makes the agent declare the
  authoritative DB, verify it (`db.getName()`, resolved connection string), fail
  loudly if the connection env var is missing, and treat any remote (Atlas) as
  READ-ONLY unless the user explicitly authorizes a write.
- Reusable, parameterized mongosh helpers for parity-check, seed, and cleanup
  replace the hand-rewritten one-offs.

## Evidence

- `Termocasa-react cd806df1` — user: "non usare il locale è obsoleto";
  "le 3 HIGH sono FALSI ALLARMI ... gli agenti hanno contato sul tcp-app-db
  locale obsoleto (705 doc), non sull'Atlas corrente (590)";
  "TCP_REACT_MONGO_CONNECTION_STRING non è presente nel mio ambiente".
- `Termocasa-react a99e5347`, `1a1d1d4b`, `ef0234e1` — parity/seed/cleanup mongosh
  rewritten by hand repeatedly.
- Full verified analysis: `reflection-notes.md` candidate #7 (Mongo topology part;
  the scaffold/permission sub-parts were confirmed already fixed upstream in PR #5).
