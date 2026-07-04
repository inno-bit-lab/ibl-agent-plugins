# Problem

## Affected Skill

- Skill: session-handoff
- Plugin: ibl-agent-workflow
- Agent/Host: claude (observed); the issue itself is host-agnostic

## What Happened

The skill works in its core, but two frictions recur on essentially every
invocation, plus three smaller ones.

1. **Destination.** The skill hard-codes "never save into the workspace/repo"
   (SKILL.md step 5 and the frontmatter `description`), but in practice the user
   overrides this by voice in all observed write invocations, asking for the doc
   in the repo under `docs/handoff/` so it is versioned. In one session the doc
   was written to the OS temp dir, the user asked "dove sta handoff?" then
   "mettilo in docs di progetto", forcing a manual copy + commit.

2. **Agentic strategy section.** The template has no section capturing the tiered
   model/agent strategy in flight (which agent orchestrates and never delegates
   review, which agents/subagents are running). The user adds it post-hoc via
   Edit and then pre-emptively asks for it in the args of every later invocation.

3. **Detail level** requested manually more than once ("deve essere estremamente
   dettagliato ... trappole e rischi").

4. **Redaction false positive:** an `author_session` slug ("sonar-cleanup") was
   redacted as if it were a secret.

5. **Resume:** no explicit step to confirm the `previous_handoff` path exists
   before searching for it, and the destination name drifts (docs/handoff vs
   docs/handoffs).

## Expected Behavior

- Destination is an explicit choice with a versioned default the user actually
  wants, and the final path is written into the output.
- The template captures the agentic strategy as a first-class section.
- A completeness checklist (traps, risks, open tasks) is part of the quality bar.
- Redaction does not flag branch names / session ids / slug identifiers.
- The resume note checks the previous-handoff path exists before opening it.

## Evidence

- Session transcripts under `~/.claude/projects` (verified in Capture analysis):
  - `Ibl360 4da8b12a` — "nell'handof non è esplicitata la strategia agentica
    scrivila qui" (section added by hand).
  - `Ibl360 f836c207`, `Notarius 657010fc` — same request pre-emptively in the
    invocation args (3 sessions total).
  - `Ibl360 91f6ff97` — doc written to temp; "dove sta handoff?" → "mettilo in
    docs di progetto" → manual copy to `docs/handoff` + commit c704e6b.
  - `Sonar 1f5cbf14` — redaction false positive on author_session "sonar-cleanup";
    detail level requested manually (repeated in `28e17dc7`).
- Files involved: `assets/handoff-template.md`, `SKILL.md` (step 5 + description),
  `references/redaction.md`.
- Full verified analysis: `reflection-notes.md` candidate #8 (6 sessions, ~10
  friction events; the "resume failed" claim was rejected as a cross-project mix-up).
