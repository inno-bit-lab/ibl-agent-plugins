# Improvement

## Proposed Change

New skill `plugins/ibl-agent-workflow/skills/agentic-orchestration/`:

- `SKILL.md` (host-agnostic overview): model tiering expressed as a **PRINCIPLE**
  (a fixed orchestrator that never delegates review/verdicts; the most capable
  model for critical/adversarial tasks; a cheap model for reports/lint) — **not**
  the Fable/Opus/Sonnet names; the disjoint-scope rule for parallelism; a
  self-contained subagent briefing; consolidation into a master file; a
  declared-autonomy protocol.
- `references/` for the details: a resume checklist (worktree state, tasks in
  flight, scratch cleanup) and the **verified** failure modes only (degenerate
  output; a dispatch that wrote zero files → confirm files were actually touched
  via `git status`; orphan tasks visible from another session).
- Register the skill in `PLUGIN_SKILLS` in `tools/validate-plugin.py`. The three
  manifests already point at `./skills/`, so no manifest edit is needed for
  presence (Codex `defaultPrompt` already has its 3 entries).

## Rationale

Host-agnostic when written as a principle: it is prose any host (Codex, Claude
Code, Antigravity, OpenCode) can follow. This is the broadest pattern in the
corpus (26 sessions, ~10 projects) and today costs the user a manual
re-injection every session.

## Scope

- In: `SKILL.md` pattern + `references/` + the `PLUGIN_SKILLS` entry.
- Out (device / Claude-Code-specific, NOT in this skill): the SDD `task_close`
  and `dispatch_health_check` scripts — they depend on superpowers' `progress.md`
  format and Claude Code task/workflow tooling, so they are not portable. Keep
  them as the user's device tooling, or describe the checks as generic prose.

## Risks

- Discovery overlap with `superpowers:dispatching-parallel-agents` and
  `subagent-driven-development`: write the `description` to differentiate
  (tiering + SDD close + resume) without contradicting those third-party skills.
- Do NOT copy the rejected claims (watchdog 600s, 0 tool_uses, "15 times") — they
  would undermine the skill's credibility.
- Decide that this skill becomes canonical and MEMORY.md /
  agentic-model-tiering.md become pointers to it, or they will diverge.
- On apply (Process Mode), the skill folder AND the `PLUGIN_SKILLS` entry must
  land together, or `tools/validate-plugin.py` fails ("missing/unexpected skill").
