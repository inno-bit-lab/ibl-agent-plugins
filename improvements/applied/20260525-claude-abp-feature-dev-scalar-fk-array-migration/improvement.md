# Improvement

## Proposed Change

Import the Claude Code data migration guidance into the canonical `abp-feature-dev` skill:

- Add scalar FK to FK array as a recognized refactor class.
- Add a MongoDB migration recipe using per-document `$set` and `$unset`.
- Add sanity sweep queries.
- Add multikey index rebuild guidance.
- Add frontend pairing notes for API client and form schema changes.

## Rationale

Without this guidance, existing MongoDB documents can silently lose visible associations after the backend refactor because the new array field deserializes empty while the old scalar field is ignored.

## Scope

ABP feature development reference documentation only.

## Risks

Low. This is documentation/reference guidance and does not alter executable project code.
