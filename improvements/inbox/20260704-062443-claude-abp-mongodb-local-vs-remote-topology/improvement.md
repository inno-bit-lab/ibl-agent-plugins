# Improvement

## Proposed Change

1. New `references/local-vs-remote-topology.md`: a "source of truth" protocol —
   before any audit/migration/count, **declare the authoritative database** and
   verify it (`db.getName()`, echo the resolved connection-string name), require
   the connection env var to be present (fail loudly if absent), and treat the
   remote/Atlas as **READ-ONLY** unless the user explicitly authorizes a write.
   Include the local-vs-Atlas false-HIGH audit as the worked failure example.

2. Parameterized mongosh helpers (templates in the reference, optionally a
   `scripts/` wrapper) for parity-check (count/field diffs between two targets),
   seed, and cleanup — using placeholders resolved via `abp_context`
   (project / DB / collection names), never hard-coded DB names.

3. Cross-link the new reference from `SKILL.md` (a short "Which database am I
   talking to?" note near the top, plus an entry under "What this skill does NOT
   cover" pointing here for topology/authority).

## Rationale

Host-agnostic: mongosh is external to the agent, so the deliverable is prose +
JS templates any host (Codex, Claude Code, Antigravity, OpenCode) can run. The
failure it prevents — false HIGH findings computed against the wrong database —
is high-severity and cost the user an explicit interrupt.

## Scope

- In: topology / source-of-truth reference + parameterized mongosh parity/seed/
  cleanup helpers + a `SKILL.md` cross-link.
- Out: Atlas Search / Vector / Stream (still delegated to `mongodb:*` skills);
  schema design; query optimization.

## Risks

- Helpers must be parameterized with `abp_context` placeholders, never hard-coded
  Termocasa DB/collection names, or they are not reusable.
- The reference MUST impose read-only on the remote to avoid accidental writes to
  a production Atlas cluster.
- Keep it about *topology / authority*, not Atlas features already delegated to
  the `mongodb:*` skills, to avoid trigger overlap.
