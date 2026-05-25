# Modified Resources

- `plugins/ibl-abp/skills/abp-feature-dev/SKILL.md`
- `plugins/ibl-abp/skills/abp-testing/SKILL.md`
- `plugins/ibl-abp/skills/abp-react-ui/references/page-pattern.md`
- Optional: `plugins/ibl-abp/skills/abp-feature-dev/scripts/verify_feature.py`

## Notes

- `abp-feature-dev/SKILL.md` should own the explicit user decision and final
  handoff requirements.
- `abp-testing/SKILL.md` may need a clearer default backend CRUD/lifecycle/
  multitenancy matrix so the orchestrator can delegate consistently.
- `abp-react-ui/references/page-pattern.md` already mentions page tests, but
  should define the expected minimum CRUD page test coverage if frontend tests
  are selected.
- `verify_feature.py` can remain unchanged initially. A later enhancement could
  add an optional `--test-scope backend|frontend|both|none` check that verifies
  expected test files exist when tests were selected.
