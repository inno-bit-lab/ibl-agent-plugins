# Improvement

## Proposed Change

1. **`assets/handoff-template.md`** — add a short required "Agentic strategy"
   section (tiered model roles expressed as principle, which agent orchestrates
   and never delegates review, agents/subagents in flight), and turn the
   traps / risks / open-tasks sections into an explicit completeness checklist
   referenced from the SKILL.md "Quality bar".

2. **`SKILL.md` step 5 + frontmatter `description`** — replace the absolute
   "never save into the workspace/repo" with an explicit destination choice:
   default to a versioned repo path (`docs/handoff/` with a canonical dated
   filename), OS temp dir as fallback, always write the final path into the
   output, and keep the redaction pass mandatory before writing. Fix ONE
   canonical directory name to end the `docs/handoff` vs `docs/handoffs` drift.

3. **`references/redaction.md`** — extend the "don't over-redact ordinary
   identifiers" whitelist (principle 4) to explicitly include branch names,
   session ids, and `author_session`/slug identifiers, so they are not treated
   as secrets.

4. **template NEXT AGENT block** — add a resume note: verify the
   `previous_handoff` path exists before trying to open it.

## Rationale

Frictions 1 and 2 occur on 100% of observed write invocations, and the current
source directly conflicts with the user's real workflow (versioned handoffs).
Every change is to Markdown template/prose, so it applies identically on Codex,
Claude Code, Antigravity, and OpenCode — host-agnostic, no runtime dependency.

## Scope

- In: template (strategy section, completeness checklist, resume note),
  SKILL.md step 5 + description, redaction.md whitelist.
- Out: the redaction *script* logic (frictions are in prose guidance, not the
  scanner); `references/suggested-skills.md`.

## Risks

- The "never in repo" default is a deliberate safety choice (handoffs carry
  redacted-but-sensitive context). Making `docs/handoff` the default MUST keep
  the redaction pass mandatory before writing, or sensitive context could land
  in shared repos (e.g. BMW/CDXCALL). Prefer an explicit/configurable
  destination, not a silent flip.
- Keep the "Agentic strategy" section short to respect the skill's core
  principle ("transfer only what is not recoverable").
- The `description` edit must stay within the 1024-char frontmatter limit
  enforced by `tools/validate-plugin.py`.
