# Validation

## Checks Run

- [x] Improvement artifact validated
- [x] Skill frontmatter validated after applying the candidate change
- [x] Plugin manifest validated after applying the candidate change
- [x] Relevant scripts compiled or tested

## Commands

```powershell
python plugins\ibl-skill-improvement\skills\skill-improvement\scripts\improvement_inbox.py validate improvements\applied\20260525-174322-antigravity-abp-testing-mongodb-background-services-like-mongosandbox-cause-coverlet-col
python tools\validate-plugin.py
python C:\Users\Innotech\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\ibl-abp\skills\abp-testing
python C:\Users\Innotech\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\ibl-abp
python -m py_compile plugins\ibl-abp\skills\abp-testing\scripts\scaffold_test.py
git diff --check
```

## Result

Applied and validated.
