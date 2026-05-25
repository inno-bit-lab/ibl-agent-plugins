# Modified Resources

- `plugins/ibl-abp/skills/abp-feature-dev/SKILL.md`
- `plugins/ibl-abp/skills/abp-testing/SKILL.md`
- `plugins/ibl-abp/skills/abp-testing/scripts/scaffold_test.py`
- `plugins/ibl-abp/skills/abp-testing/templates/AppServiceTest.cs.tmpl`
- `plugins/ibl-abp/skills/abp-react-ui/references/page-pattern.md`
- `plugins/ibl-abp/.codex-plugin/plugin.json`
- `plugins/ibl-abp/.claude-plugin/plugin.json`
- `plugins/ibl-abp/plugin.json`

## Notes

- `abp-feature-dev/SKILL.md` should own the explicit user decision and final
  handoff requirements.
- `abp-testing/SKILL.md` may need a clearer default backend CRUD/lifecycle/
  multitenancy matrix so the orchestrator can delegate consistently.
- `abp-react-ui/references/page-pattern.md` already mentions page tests, but
  should define the expected minimum CRUD page test coverage if frontend tests
  are selected.
- `abp-testing/scripts/scaffold_test.py` and its template were updated because
  the backend CRUD matrix should match what the orchestrator now delegates.
- `verify_feature.py` remains unchanged. A later enhancement could add an
  optional `--test-scope backend|frontend|both|none` check that verifies
  expected test files exist when tests were selected.
