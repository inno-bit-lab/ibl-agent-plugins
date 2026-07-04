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

## Result

Pending — proposal only (Capture Mode). Not applied to canonical skill.
