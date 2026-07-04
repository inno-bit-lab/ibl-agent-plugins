# Validation

## Checks Run

- [x] Skill frontmatter validated
- [x] New reference reviewed for host-agnostic phrasing (mongosh templates, no Claude-only tools)
- [x] mongosh helpers use `abp_context` placeholders, not hard-coded DB names
- [x] Read-only-on-remote rule present and unambiguous
- [x] Canonical patch applied to `plugins/ibl-abp/skills/abp-mongodb/`

## Commands

```powershell
python tools/validate-plugin.py
python C:\Users\Innotech\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins/ibl-abp
```

## Artifact structure

`improvement_inbox.py validate improvements/inbox/<this-artifact>` → `[OK]` (2026-07-04);
`python tools/validate-plugin.py` runs green on the unmodified tree.

## Result

Applied 2026-07-04 in Process Mode. Canonical patch validated and ready to move
from `improvements/inbox/` to `improvements/applied/`.
