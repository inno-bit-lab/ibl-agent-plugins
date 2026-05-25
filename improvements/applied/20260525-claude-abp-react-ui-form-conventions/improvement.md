# Improvement

## Proposed Change

Import the Claude Code improvements into the canonical `abp-react-ui` skill:

- Add the remount-on-id edit form rule to `SKILL.md`.
- Require shared `<Field>` usage in form fields.
- Rewrite form error handling guidance around the shared `<Field>` primitive.
- Document Radix Select rules and the stale-controller failure mode.
- Replace complex edit page structure guidance with an outer wrapper plus remount-keyed inner form pattern.
- Add `<Field>` to the shared components reference.

## Rationale

These conventions prevent repeated UI regressions around ABP edit pages, Radix Select, and duplicated form field markup.

## Scope

React UI skill documentation only.

## Risks

Low. This is documentation/reference guidance and does not alter executable project code.
