# Validation

## Checks Run

- [ ] Skill frontmatter validated
- [ ] New reference reviewed for host-agnostic phrasing (no `preview_*` tool names)
- [ ] Rejected claims (password-grant/.Trim, dev-cert-not-trusted, "12 timeouts") absent
- [ ] SKILL.md Verify/Polish link points to the new reference

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
