# Validation

## Checks Run

- [ ] Skill frontmatter validated
- [ ] New reference reviewed for host-agnostic phrasing (mongosh templates, no Claude-only tools)
- [ ] mongosh helpers use `abp_context` placeholders, not hard-coded DB names
- [ ] Read-only-on-remote rule present and unambiguous

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
