# Validation

## Checks Run

- [ ] Skill frontmatter validated (`description` <= 1024 chars after edit)
- [ ] Template + references reviewed for host-agnostic phrasing (no Claude-only tools)
- [ ] Redaction whitelist change does not weaken secret detection
- [ ] `evals/evals.json` still consistent with the new destination behavior

## Commands

```powershell
python tools/validate-plugin.py
```

## Artifact structure

`improvement_inbox.py validate improvements/inbox/<this-artifact>` → `[OK]` (2026-07-04);
`python tools/validate-plugin.py` runs green on the unmodified tree.

## Result

Canonical-patch validation is Pending — this is a proposal only (Capture Mode),
not applied to the canonical skill.
