# Problem

## Affected Skill

- Skill: agentic-orchestration (NEW)
- Plugin: ibl-agent-workflow
- Agent/Host: claude (observed); the skill must be written host-agnostically

## What Happened

The user's most effective way of working is not captured as a skill: parallel
multi-agent dispatch on disjoint file scopes with a critical final consolidator,
plus explicit model tiering (a fixed orchestrator that never delegates review;
the most capable model for critical/adversarial tasks; a cheap model for
reports/lint). It lives only in MEMORY.md / agentic-model-tiering.md and is
rebuilt by hand every time:

- The "Strategia agentica adottata" table is pasted verbatim at the start of
  >= 6 sessions.
- The user interrupts to impose the model ("gli agenti dovranno essere tutti
  Opus 4.8", "lo hai avviato con Fable 5 ma non va bene").
- The post-task SDD close loop (review-package → diff → ledger → progress.md) is
  redone by hand 8-12 times per session.
- Real failure modes go uncaught: a pipeline that produced ZERO files was found
  only via `git status`; a dead workflow left orphan tasks visible only from
  another session.

## Expected Behavior

A skill that codifies the pattern host-agnostically so it does not have to be
re-injected each session.

## Evidence

- Tiering table pasted verbatim: `Ibl360 caefadfb / c48efab5 / 4da8b12a`,
  `Notarius 8fe34dae`, `ds4 50dc4901 / a29ed039`.
- Model imposed via interrupt: `Notarius 9996098a`, `657010fc`.
- Disjoint-scope dispatch + consolidator: `Termocasa 6a602745` (38 agents + 9
  fixers), `DAPP ad757128` (57 repos), `Ibl360-wt b7117dd6` (~12 SDD cycles).
- Uncaught failures: `Termocasa 80a24f77` (zero files, found via git status);
  `Notarius 657010fc` (orphan tasks cross-session).
- Full verified analysis: `reflection-notes.md` candidate #2 (26/27 sessions confirmed).

## Claims the verification REJECTED — do NOT encode

- "watchdog stall 600s" — not present in any transcript.
- "batch agent returns 0 tool_uses" — not present; the real analogues are the
  degenerate output and the zero-files pipeline.
- "measured 15 times per session" — the real figure is 8-12.
