# Validation

## Checks Run

- [ ] New skill frontmatter: `name` == folder "agentic-orchestration", `description` <= 1024 chars
- [ ] `PLUGIN_SKILLS` updated with "agentic-orchestration" under ibl-agent-workflow
- [ ] SKILL.md host-agnostic (tiering as principle, no model names, no Claude-only tools)
- [ ] Rejected claims (watchdog 600s, 0 tool_uses, "15x") absent
- [ ] `description` differentiated from superpowers dispatching/subagent skills

## Commands

```powershell
python tools/validate-plugin.py
```

## Artifact structure

`improvement_inbox.py validate improvements/inbox/<this-artifact>` → `[OK]` (2026-07-04);
`python tools/validate-plugin.py` runs green on the unmodified tree.

## Result

Canonical-patch validation is Pending — this is a proposal only (Capture Mode);
no skill folder created yet.
