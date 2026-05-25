# Improvement

## Proposed Change

Add an explicit test coverage interview step with backend/frontend/both/none choices, defaults, expected artifacts, and validation requirements.

## Rationale

The feature development workflow is already interview-driven for entity shape,
audit level, tenancy, permissions, optional endpoints, lifecycle, and React UI.
Tests should follow the same pattern. A generated AppService without test
coverage can look "done" because build and smoke validation pass, while core
business behavior remains uncovered.

The current "Suggest writing tests" instruction is too easy for agents to skip
or treat as optional afterthought. The improvement should make the test decision
explicit, record it in the summary, and tie it to concrete artifacts and
commands.

## Scope

Update `abp-feature-dev` as the orchestrator:

1. Add a new interview/finalization step: **Test coverage decision**.
2. Ask the user to choose one of:
   - `backend`
   - `frontend`
   - `both`
   - `none`
3. Apply defaults:
   - backend-only feature -> default `backend`
   - backend + React UI -> default `both`
   - no test infrastructure detected -> ask before scaffolding tests and record
     the missing infrastructure if the user chooses to skip
4. Delegate backend tests to `abp-testing`.
5. Delegate frontend tests to `abp-react-ui`, or add a small reference in
   `abp-react-ui` that defines the expected CRUD page test matrix.
6. Move final validation after test generation so test compilation/execution is
   included before declaring the feature complete.
7. Require final handoff to include:
   - test scope selected
   - files added/updated
   - test commands run
   - skipped coverage and reason, if any

Backend test matrix expected from `abp-testing` for a standard CRUD AppService:

- `Should_Get_List`
- `Should_Get_{Entity}`
- `Should_Create_{Entity}_When_Input_Is_Valid`
- `Should_Update_{Entity}_When_Input_Is_Valid`
- `Should_Delete_{Entity}`
- `Should_Throw_Validation_For_Invalid_Input`
- permission behavior when permission enforcement is part of the feature
- tenant isolation when the entity implements `IMultiTenant`
- lifecycle transition tests when the entity has status/state behavior
- uniqueness/business-rule `BusinessException` tests when the AppService or
  entity enforces invariants

Frontend test matrix expected when a React CRUD page is generated:

- page renders list data from the API client mock
- empty state renders
- create flow calls the create mutation with normalized DTO shape
- edit flow loads existing values and calls update
- delete flow opens confirmation and calls delete
- filters/search map to the typed backend query input
- permission-gated actions are hidden/disabled as expected
- lifecycle/status action renders allowed transitions and surfaces backend
  `BusinessException` messages when applicable

Suggested wording for `abp-feature-dev/SKILL.md`:

```markdown
10. **Ask for test coverage.** Do not silently skip this step.

If the user already explicitly requested or rejected tests, honor that. Otherwise ask:

Do you want tests for {Entity}?
  - backend   -> ABP integration tests for AppService/domain behavior
  - frontend  -> React/Vitest tests for the CRUD page
  - both      -> backend + frontend tests
  - none      -> skip tests; final handoff will mention this gap
[default: backend for backend-only features; both when React UI was generated
 and the frontend test setup is healthy]

If backend or both: delegate to `abp-testing` and create/update
`{TestProject}/{Plural}/{Entity}AppService_Tests.cs`.

If frontend or both: delegate to `abp-react-ui` and create/update
`react/src/pages/{plural}/{Entity}Page.test.tsx` or the equivalent tests for
dedicated create/edit pages.

If tests cannot be added because the existing test setup is broken, report the
pre-existing failure and ask whether to add only the unaffected side.
```

Suggested final validation update:

```markdown
Run `dotnet test` when backend tests were selected.
Run `npm run test:run -- <changed test files>` or the project's equivalent when
frontend tests were selected.
If a broader frontend build/test command fails due to pre-existing unrelated
errors, identify the unrelated files and still report whether the new tests
compile/run when possible.
```

Suggested deletion/refactor addition:

```markdown
The impact map must include backend and frontend tests. Delete obsolete tests
when the feature is removed; update tests when DTOs, permissions, filters,
routes, or lifecycle behavior changes.
```

## Risks

- Asking one more question can slow simple scaffolds. Mitigation: provide clear
  defaults and let the user answer "default".
- Frontend test infrastructure may be flaky or already broken. Mitigation:
  separate backend and frontend choices, and require the agent to report
  pre-existing failures rather than silently skipping tests.
- Over-scaffolding low-value frontend tests can create maintenance cost.
  Mitigation: keep frontend tests focused on the generated page contract and
  user-visible CRUD flows, not exhaustive component internals.

