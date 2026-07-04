# Validation

## Checks Run

- [x] Skill frontmatter validated (`description` <= 1024 chars after edit)
- [x] Template + references reviewed for host-agnostic phrasing (no Claude-only tools)
- [x] Redaction whitelist change does not weaken secret detection
- [x] `evals/evals.json` still consistent with the new destination behavior
- [x] Canonical patch applied to `plugins/ibl-agent-workflow/skills/session-handoff/`

## Commands

```powershell
python tools/validate-plugin.py
python C:\Users\Innotech\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins/ibl-agent-workflow
```

## Artifact structure

`improvement_inbox.py validate improvements/inbox/<this-artifact>` → `[OK]` (2026-07-04);
`python tools/validate-plugin.py` runs green on the unmodified tree.

## Result

Applied 2026-07-04 in Process Mode. Canonical patch validated and ready to move
from `improvements/inbox/` to `improvements/applied/`.
