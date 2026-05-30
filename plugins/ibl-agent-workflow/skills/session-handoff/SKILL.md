---
name: session-handoff
description: 'Write a handoff (continuity) document that summarises the current session so a FRESH agent — new context window, no memory of this chat — can pick up the work. Saves the doc to the OS temp directory (never the workspace), redacts secrets and PII, references existing artifacts (PRDs, plans, ADRs, issues, commits, diffs) by path or URL instead of duplicating them, and includes a "Suggested skills" section pointing the next agent at the skills to invoke. Use whenever the user wants to hand off, pause, wrap up, or resume work later — phrases like "write a handoff", "create a handoff doc", "summarise this session for another agent", "I''m running low on context", "document where we are so I can continue tomorrow", "prepare a continuation prompt", or before /clear or context compaction. If the user passes arguments, treat them as what the next session will focus on and tailor the doc to that.'
---

# Session handoff

Write a document that lets a fresh agent — one with **no memory of this
conversation** — continue the work without re-deriving everything.

## The one principle that drives everything

**Transfer only what is NOT recoverable from the repo.** A capable fresh agent
can read the code, run `ls`, and re-derive architecture. It cannot recover what
lived only in this conversation: the intent, the decisions and their *why*, the
dead-ends already tried, what's broken right now, and the single agreed next
move. Spend the document on those. Re-summarising committed code, the file tree,
or an issue's text is the dominant failure mode — it wastes tokens and, worse,
drifts out of date and gets trusted as truth.

## Workflow

Follow these steps in order. Steps 2–4 each have a reference file with the
detail; read it when you reach that step.

1. **Gather the session state.** Walk the checklist in
   `references/state-capture.md`: git state, build/test status, work in flight
   (files + intent), decisions + rationale, dead-ends, open questions, and the
   one concrete next action. Pull real values — run `git status`,
   `git log --oneline -5`, `git stash list`, and the project's build/test
   commands rather than guessing.

2. **Apply the dedup rule.** For each fact, decide *capture vs link* using the
   procedure in `references/state-capture.md` ("The dedup rule, operationalised").
   In short: if it already lives in a commit / diff / PR / issue / ADR / PRD /
   plan, **link it and write only the one-line delta** — never copy its body.

3. **Draft the document** from `assets/handoff-template.md`. Keep the order:
   front-load the action, push reconstructable detail and links to the bottom.
   The structure and why each section exists is in
   `references/state-capture.md`; the suggested-skills section has its own guide
   in `references/suggested-skills.md`.

4. **Redact.** Run the bundled script over the finished draft, then do the
   contextual PII pass the script can't: see `references/redaction.md`.

   ```bash
   python <skill-dir>/scripts/handoff.py redact <draft-path>
   ```

5. **Save to the OS temp directory and report.** Get the target path from the
   helper (it resolves the OS temp dir cross-platform — `%TEMP%` on Windows,
   `$TMPDIR`/`/tmp` elsewhere — and creates the folder):

   ```bash
   python <skill-dir>/scripts/handoff.py path --slug "<short-topic>"
   ```

   Write the doc there, run the redact pass on that file, then tell the user the
   absolute path. **Never save the handoff into the workspace/repo** — it is
   ephemeral session state and may contain redacted-but-sensitive context; the
   temp directory keeps it out of commits.

## What goes at the very top

Two things a fresh agent needs before anything else, so put them first:

- **The next action**, as line 1 of the body: one imperative sentence naming the
  exact file/test/command, with a pass/fail "done when" and a verify command.
  This is the single most valuable line in the document — it's the thing that
  existed only in this conversation and is gone the moment context resets.
- **A "Verify first" block**: the handoff is a snapshot that may already be
  stale when read. Tell the next agent to run `git status`, the build, and the
  tests and reconcile against the doc *before* trusting it. Tag volatile claims
  with freshness flags (✅ verified / ⚠️ not re-run / ❓ assumed).

## Machine-readable frontmatter

Start the doc with the YAML frontmatter from the template (`doc_type`, `status`,
`next_action`, `suggested_skills`, `key_files`, `verify`, …). It lets the next
agent (or a script) parse the critical fields without reading prose, and makes
staleness detectable via `base_sha`. Duplicate the same essentials in the prose
TL;DR so nothing is lost if a parser chokes on the YAML.

## Tailoring to user arguments

If the user passed arguments, treat them as **the focus of the next session**,
not as the topic of the whole document. Keep the full state capture, but:

- Make the **next action** and the ordered backlog serve that focus.
- Pull the parts of the state most relevant to that focus toward the top.
- Choose **suggested skills** that serve that focus first.

Example: args = "focus on writing the integration tests" → the next action
becomes the first failing test to write, the suggested skills lead with the
testing skill, and the backlog is the remaining test cases — even if the session
also touched other things.

## Suggested skills section

Required. List the 2–4 skills the next agent should invoke, **mapped to the next
actions** (not a generic catalog), with namespaced names and a fallback for each
in case the next session doesn't have that skill. Full guidance — including how
to enumerate available skills and why the next session's set may differ — is in
`references/suggested-skills.md`.

## Quality bar

A good handoff passes this test: a fresh agent reading only the frontmatter +
the next action + the verify block could start working correctly. Everything
below earns its place by being non-recoverable from the repo. If a section just
restates what `git diff` or an issue already says, cut it and link instead.
