# Validation

## Checks Run

- [x] New skill frontmatter: `name` == folder "agentic-orchestration", `description` <= 1024 chars
- [x] `PLUGIN_SKILLS` updated with "agentic-orchestration" under ibl-agent-workflow
- [x] SKILL.md host-agnostic (tiering as principle, no model names, no Claude-only tools)
- [x] Rejected claims (watchdog 600s, 0 tool_uses, "15x") absent
- [x] `description` differentiated from superpowers dispatching/subagent skills
- [x] Canonical patch applied to `plugins/ibl-agent-workflow/skills/agentic-orchestration/` and `tools/validate-plugin.py`

## Commands

```powershell
python tools/validate-plugin.py
python -m py_compile tools/validate-plugin.py
python C:\Users\Innotech\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins/ibl-agent-workflow
```

## Artifact structure

`improvement_inbox.py validate improvements/inbox/<this-artifact>` → `[OK]` (2026-07-04);
`python tools/validate-plugin.py` runs green on the unmodified tree.

## Result

Applied 2026-07-04 in Process Mode. Canonical patch validated and ready to move
from `improvements/inbox/` to `improvements/applied/`.
