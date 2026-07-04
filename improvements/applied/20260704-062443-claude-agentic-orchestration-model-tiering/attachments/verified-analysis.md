# Verified analysis — agentic-orchestration (model tiering)

Self-contained excerpt of the adversarially-verified reflection for this artifact.

## Summary

The user's most effective way of working (parallel dispatch on disjoint scopes +
critical consolidator + explicit model tiering) is not a skill; it is rebuilt by
hand every session.

## Evidence

- Tiering table pasted verbatim at session start (>= 6 sessions): `Ibl360 caefadfb / c48efab5 / 4da8b12a`, `Notarius 8fe34dae`, `ds4 50dc4901 / a29ed039`.
- Model imposed via interrupt: `Notarius 9996098a` (stop-hook: full autonomy + all Opus 4.8), `657010fc` ("lo hai avviato con Fable 5 ma non va bene").
- "salvati la strategia agentica" + manual SDD loop ~9 tasks: `Ibl360 f836c207`.
- Disjoint-scope dispatch + consolidator: `Termocasa 6a602745` (38 agents + 9 fixers), `DAPP ad757128` (57 repos KT), `Ibl360-wt b7117dd6` (~12 SDD cycles).
- Uncaught failures: `Termocasa 80a24f77` (pipeline wrote ZERO files, found via git status), `Notarius 657010fc` (orphan tasks cross-session), `snam b3d1bd4f` (degenerate agent output).

## Adversarial verification

- Confirmed: 26 of 27 cited sessions, across ~10 projects. Broadest pattern in the corpus.
- Rejected session: `ds4 4d0df1f3` (a /init session, no orchestration).

## Claims REJECTED by verification — do NOT encode

- "watchdog stall 600s" — not present in any transcript.
- "batch agent returns 0 tool_uses" — not present; the real analogues are the degenerate output and the zero-files pipeline.
- "measured 15 times per session" — the real figure is 8-12.

## Caveats for the processor

- Express tiering as a PRINCIPLE, not Fable/Opus/Sonnet names (host-agnostic).
- Exclude the non-portable SDD `task_close` / `dispatch_health_check` scripts (they
  depend on superpowers `progress.md` and Claude Code task tooling) — describe the
  checks as generic prose instead.
- Differentiate the `description` from superpowers:dispatching-parallel-agents and
  subagent-driven-development.
- On apply, the skill folder AND the `PLUGIN_SKILLS` entry must land together.

Source: reflection over `~/.claude` session transcripts. Session ids are opaque; no secrets present.
