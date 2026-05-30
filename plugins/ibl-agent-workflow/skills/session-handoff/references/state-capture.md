# State capture & the dedup rule

What a fresh agent needs to resume coding, and how to avoid duplicating what
already lives in durable artifacts.

## The governing idea: two axes

Every fact you might write falls on two axes. Your unique value is the
bottom-right cell — everything in the "durable artifact" column is a dedup
hazard.

| | Lives in a durable artifact | Lives only in the session / live machine |
|---|---|---|
| **Stable** | → **LINK** (ADR, PRD, README, plan) | → write once (architecture mental model) |
| **Volatile** | → **POINT + one-line delta** (commit SHA, diff, PR, issue) | → **CAPTURE in full** (uncommitted changes, dead-ends, running processes, open questions) |

## State-capture checklist

Capture what is volatile and lives nowhere else; link the rest.

**Git / VCS** — current branch + upstream; last commit SHA (anchor); uncommitted
changes (modified/staged files, one-line *intent* per file, not a re-described
diff); stashes (`git stash list`); untracked files that matter; in-progress
rebase/merge state; open PR URL + CI status (link, don't transcribe).

**Build / test / run** — does it compile now? exact command. Test pass/fail
counts, which suites are green, **which specific tests fail and why**, exact
command to reproduce. Was the last commit green (did I break it this session or
was it already red)? Lint/typecheck if relevant. Tag each with a freshness flag.

**Environment & access (presence, never values)** — which env vars are required
and whether they are present; which credentials/logins the session used (e.g.
"gh authenticated ✅", "DB connection string present in `.env` ✅") — never the
secret itself; services the work depends on (DB reachable? migrations applied?
seed loaded?); toolchain versions if non-obvious (or link `.nvmrc`/`global.json`).

**Work in flight** — the exact files in flight, each with *what was being done
and how far it got* (intent, not content). Prefer function/symbol names with
approximate location over raw line numbers (they drift). State the scope
boundary: what is in this unit of work vs deferred.

**Decisions & rationale** — each decision as *decision → one-line why* (capture
the why, not just the outcome). For anything ADR-worthy, write the ADR and link
it. List assumptions the work rests on that could be wrong. Record the
architecture mental model built this session that is NOT obvious from the code.

**Open questions & dead-ends** — open questions (with who/what could answer
them). **Dead-ends already tried** — the highest-leverage section: *approach →
why it failed → don't retry unless X changes*; without it the next agent burns
time rediscovering the same dead ends. "Do-not-touch / looks-broken-but-isn't"
guardrails.

**Next concrete action + verification** — exactly one unambiguous imperative
("write the failing test for tenant-scoping in `auth/middleware.test.ts`
asserting a cross-tenant request returns 403", not "continue the auth work"); a
pass/fail definition of done; the verify command(s); then a short ordered
backlog so the agent has runway past step 1.

## The dedup rule, operationalised

For each fact you are about to write, ask in order:

1. **Does it already live in a durable, addressable artifact** (commit, diff,
   PR, issue, ADR, PRD, plan, README, `.env.example`)?
   - **No** → it's session-volatile → **capture in full.**
   - **Yes** → go to 2.
2. **Will the next agent act differently depending on its content?**
   - **No** → **link only** (path / URL / SHA), one line of context max.
   - **Yes** → **link it + add only the one-line delta** (the outcome and where
     we are relative to it). Never reproduce the artifact's body.

In one sentence: *link to evidence and context; capture only the delta and the
things that exist nowhere but here.*

| Situation | ❌ Don't | ✅ Do |
|---|---|---|
| Auth approach decided | Re-explain trade-offs over 3 paragraphs | "JWT-per-tenant (see `docs/adr/0007.md`). At: middleware written, tests pending." |
| Changed 6 files | Describe each change in prose | "Changes on top of `a1b2c3d` — see `git diff a1b2c3d` / PR #214. Intent per file: <3-line list of *why*>." |
| A GitHub issue exists | Paste the issue body | "Implements #88. Beyond the issue: the rate-limiter must be tenant-aware." |
| A plan/PRD exists | Re-summarize the plan | "Executing `plans/checkout.md` phase 2/4, task 2.3." |
| Codebase layout | Restate the file tree | Omit — point only to the one non-obvious entry point. |

Why re-summarising is harmful: **drift** (summary and source diverge the moment
either changes), **staleness** (stale context spoken as truth is worse than no
context), and **wasted tokens** (a SHA/URL is a few tokens and is always current).

## Anti-patterns (call these out)

- Restating the file tree / directory listing — the agent can `ls`.
- Re-describing committed code in prose — point at the diff by SHA.
- Copying issue / ticket / PRD text — link it, record only what was learned beyond it.
- Vague next steps ("finish the tests", "clean up") — unverifiable; force re-derivation.
- Summarizing the plan/ADR you're executing — link it, give your position in it.
- Recording secret values "for convenience" — presence/absence only.
- Line numbers as the primary anchor — they drift; prefer symbol names.

## Make the doc self-distrusting

A handoff is a snapshot that may already be stale when read. Two safeguards:

1. **Freshness flags** on every volatile claim: ✅ verified this session /
   ⚠️ observed earlier, not re-verified / ❓ assumed, needs validation. This
   tells the next agent what to re-check first.
2. **A "Verify first" startup block** at the top of the resume flow (git status,
   git stash list, build, test, env presence, confirm referenced files still
   exist). Rule: **if any check disagrees with the snapshot, trust the live
   repo/tests and flag that section as stale before proceeding.**
