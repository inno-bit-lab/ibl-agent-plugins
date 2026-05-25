# Validation

## Checks Run

- [x] Skill frontmatter validated
- [x] Plugin manifest validated
- [x] Relevant scripts compiled or tested
- [x] Regression evidence added

## Commands

```powershell
python tools/validate-plugin.py
python C:\Users\Innotech\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\ibl-skill-improvement\skills\skill-improvement
python C:\Users\Innotech\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\ibl-skill-improvement
python -m py_compile plugins\ibl-skill-improvement\skills\skill-improvement\scripts\improvement_inbox.py
python plugins\ibl-skill-improvement\skills\skill-improvement\scripts\improvement_inbox.py publish --help
```

## Result

Passed.
