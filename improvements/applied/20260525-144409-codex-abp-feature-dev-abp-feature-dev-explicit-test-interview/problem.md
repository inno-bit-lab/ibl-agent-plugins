# Problem

## Affected Skill

- Skill: abp-feature-dev
- Plugin: ibl-abp
- Agent/Host: codex

## What Happened

abp-feature-dev only says to suggest tests after scaffolding, so new ABP entities can be completed without asking whether to create backend or frontend tests.

## Expected Behavior

When `abp-feature-dev` is used to create or port an entity/AppService, the
workflow should not silently finish without a test decision.

After backend scaffolding and after any React UI decision, the agent should ask
an explicit test coverage question unless the user already made the answer
unambiguous:

```text
Do you want tests for {Entity}?
  - backend   -> ABP integration tests for the AppService/domain behavior
  - frontend  -> React/Vitest tests for the generated CRUD page
  - both      -> backend + frontend tests
  - none      -> skip tests; final handoff must mention the skipped coverage
[default: backend for backend-only features; both when React UI was generated
 and the frontend test setup is healthy]
```

The selected test scope should become part of the confirmed feature summary and
the final handoff. If tests are skipped, the final response must say that this
was an explicit choice or explain the blocker.

For deletion/refactor workflows, the skill should also require updating or
removing affected tests as part of the impact map.

## Evidence

- Command/request: user asked whether entities created with `abp-feature-dev`
  had tests and whether the skill should have asked about backend/frontend/both.
- Observed result in Ibl360: business entities had AppServices and React pages,
  but no dedicated tests for `Customer`, `Account`, `Contact`, `Supplier`, or
  `Employee`.
- Existing skill evidence:
  - `plugins/ibl-abp/skills/abp-feature-dev/SKILL.md` delegates integration
    tests to `abp-testing`.
  - The same file has a weak post-step "Suggest writing tests" instruction,
    but no explicit user choice, default, or required handoff wording.
  - `abp-react-ui/references/page-pattern.md` mentions frontend page tests, but
    it is not surfaced as a mandatory decision from `abp-feature-dev`.
