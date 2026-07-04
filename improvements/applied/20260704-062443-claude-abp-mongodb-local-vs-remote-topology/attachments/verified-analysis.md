# Verified analysis — abp-mongodb local-vs-remote topology

Self-contained excerpt of the adversarially-verified reflection for the MongoDB
topology gap. (The broader "gap ibl-abp" candidate also covered scaffold /
permission items that verification found ALREADY FIXED upstream in PR #5; those
are intentionally out of scope here.)

## Summary

abp-mongodb has no guidance on which database is authoritative when a project has
both a stale local Mongo and a current remote (Atlas). This produced a real,
high-severity failure.

## Evidence

- `Termocasa-react cd806df1` — a multi-agent audit produced 3 HIGH findings, ALL
  false because counted on the stale local `tcp-app-db` (705 docs) instead of the
  current Atlas db (590). User interrupt: "non usare il locale è obsoleto". The
  connection env var `TCP_REACT_MONGO_CONNECTION_STRING` was absent from the environment.
- `Termocasa-react a99e5347`, `1a1d1d4b`, `ef0234e1` — parity/seed/cleanup mongosh
  rewritten by hand 3-5 times per session.
- `Ibl360 9d957bb9` — hallucinated `ConfigureCollection` API (a separate abp-mongodb
  issue, already covered by the skill's existing Indexes section).

## Repo check at capture time

- `grep` over `plugins/ibl-abp/skills/abp-mongodb/`: ZERO occurrences of "mongosh";
  no `db.getName` / source-of-truth / read-only guidance. Gap confirmed real.

## Caveats for the processor

- mongosh helpers must be parameterized via `abp_context` placeholders, never
  hard-coded Termocasa DB/collection names.
- The reference MUST impose read-only on the remote (Atlas) to avoid accidental
  production writes.
- Keep it about topology/authority, not Atlas features (Search/Vector/Stream)
  already delegated to the `mongodb:*` skills.

Source: reflection over `~/.claude` session transcripts. Session ids are opaque; no secrets present.
