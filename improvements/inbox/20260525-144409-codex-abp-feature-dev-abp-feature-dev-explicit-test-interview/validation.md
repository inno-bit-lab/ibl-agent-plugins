# Validation

## Checks Run

- [ ] Improvement artifact validated
- [ ] Skill frontmatter validated after applying the candidate change
- [ ] Plugin manifest validated after applying the candidate change
- [ ] Relevant scripts compiled or tested if `verify_feature.py` is changed
- [ ] Regression evidence added with a sample feature workflow

## Commands

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py validate improvements/inbox/20260525-144409-codex-abp-feature-dev-abp-feature-dev-explicit-test-interview
python tools/validate-plugin.py
python -m py_compile plugins/ibl-abp/skills/abp-feature-dev/scripts/verify_feature.py
```

If a candidate implementation changes only markdown, `python -m py_compile`
is not required.

Recommended regression check after applying the improvement:

```powershell
# Manual workflow/read-through check:
# 1. Start an abp-feature-dev create-entity scenario.
# 2. Confirm the workflow asks for React UI.
# 3. Confirm it then asks the explicit test coverage question.
# 4. Confirm final handoff must mention selected/skipped test scope.
```

## Result

Artifact drafted; implementation not applied.
