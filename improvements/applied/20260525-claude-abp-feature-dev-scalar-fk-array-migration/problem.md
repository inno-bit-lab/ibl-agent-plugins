# Problem

## Affected Skill

- Skill: abp-feature-dev
- Plugin: ibl-abp
- Agent/Host: claude-code

## What Happened

Claude Code updated the original local `abp-feature-dev` skill after identifying a missing migration recipe for refactors from scalar foreign keys to arrays of foreign keys.

## Expected Behavior

The canonical repository should document how to migrate existing MongoDB documents, rebuild indexes, and align frontend code when a 1:N scalar FK relationship becomes N:N.

## Evidence

- Source copy: `C:\Users\Innotech\.claude\skills\abp-feature-dev\references\data-migration.md`
- Refactor class: `CustomerId?` or `SupplierId?` to `CustomerIds: List<Guid>` or `SupplierIds: List<Guid>`.
