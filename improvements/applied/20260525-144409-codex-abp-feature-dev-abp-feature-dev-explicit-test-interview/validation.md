# Validation

## Checks Run

- [x] Improvement artifact validated
- [x] Skill frontmatter validated after applying the candidate change
- [x] Plugin manifest validated after applying the candidate change
- [x] Relevant scripts compiled or tested
- [x] Regression evidence added with a sample feature workflow

## Commands

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py validate improvements/inbox/20260525-144409-codex-abp-feature-dev-abp-feature-dev-explicit-test-interview
python tools/validate-plugin.py
python C:\Users\Innotech\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\ibl-abp\skills\abp-feature-dev
python C:\Users\Innotech\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\ibl-abp\skills\abp-testing
python C:\Users\Innotech\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\ibl-abp\skills\abp-react-ui
python C:\Users\Innotech\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\ibl-abp
python -m py_compile plugins\ibl-abp\skills\abp-testing\scripts\scaffold_test.py
python plugins\ibl-skill-improvement\skills\skill-improvement\scripts\improvement_inbox.py validate improvements\applied\20260525-144409-codex-abp-feature-dev-abp-feature-dev-explicit-test-interview
git diff --check
```

Recommended regression check after applying the improvement:

```powershell
# Manual workflow/read-through check:
# 1. Start an abp-feature-dev create-entity scenario.
# 2. Confirm the workflow asks for React UI.
# 3. Confirm it then asks the explicit test coverage question.
# 4. Confirm final handoff must mention selected/skipped test scope.
```

## Result

Applied and validated.
