# Validation

## Checks Run

- [x] Skill frontmatter validated
- [x] New reference reviewed for host-agnostic phrasing (no `preview_*` tool names)
- [x] Rejected claims (password-grant/.Trim, dev-cert-not-trusted, "12 timeouts") absent
- [x] SKILL.md Verify/Polish link points to the new reference
- [x] Canonical patch applied to `plugins/ibl-abp/skills/abp-react-ui/`

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
