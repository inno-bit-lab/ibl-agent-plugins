# Verified analysis — session-handoff (destination & template)

Self-contained excerpt of the adversarially-verified reflection that produced
this artifact. These frictions are what survived verification.

## Summary

The skill works in its core, but two frictions occur on 100% of observed write
invocations, plus three smaller ones.

## Evidence (sessions cited; verbatim where quoted)

- Agentic-strategy section missing from the template, requested by hand:
  - `Ibl360 4da8b12a` — "nell'handof non è esplicitata la strategia agentica scrivila qui" (added by hand).
  - `Ibl360 f836c207`, `Notarius 657010fc` — same request pre-emptively in the invocation args (3 sessions).
- Destination overridden by voice on every write:
  - `Ibl360 91f6ff97` — doc written to OS temp; "dove sta handoff?" → "mettilo in docs di progetto" → manual copy to docs/handoff + commit c704e6b.
- Detail level forced twice: `Sonar 1f5cbf14`, `28e17dc7` ("estremamente dettagliato ... trappole e rischi").
- Redaction false positive: `Sonar 1f5cbf14` — author_session slug "sonar-cleanup" redacted as a secret.

## Adversarial verification

- Confirmed: 6 sessions, ~10 friction events, across 3 projects (Ibl360, Notarius, CDXCALL/Sonar).
- Rejected: the "resume failed" claim (`Ibl360 52059451`) was a cross-project path mix-up by the user, not a skill defect.
- The two dominant frictions (destination, agentic-strategy section) are structural and reproduce on 100% of write invocations.

## Caveats for the processor

- The "never save in the repo" default is a deliberate safety choice; changing it MUST keep the redaction pass mandatory (risk: sensitive context in shared BMW/CDXCALL repos).
- Fix ONE canonical destination name (docs/handoff vs docs/handoffs currently drift).
- Keep the frontmatter `description` <= 1024 chars (validator).

Source: reflection over `~/.claude` session transcripts (not included here for size/privacy). Session ids are opaque identifiers; no secrets are present.
