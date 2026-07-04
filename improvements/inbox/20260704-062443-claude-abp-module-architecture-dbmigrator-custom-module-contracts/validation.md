# Validation

## Checks Run

- [ ] Skill frontmatter validated
- [ ] Checklist addition reviewed for host-agnostic, parameterized phrasing
- [ ] No hard-coded solution/module names (uses `<CustomModule>Module`)

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
