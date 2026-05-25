# Problem

## Affected Skill

- Skill: abp-react-ui
- Plugin: ibl-abp
- Agent/Host: claude-code

## What Happened

Claude Code updated the original local `abp-react-ui` skill after finding recurring React form bugs around edit-mode Radix Select fields and duplicated local form field wrappers.

## Expected Behavior

The canonical repository should capture those fixes so every agent consuming `ibl-abp` uses the same React UI conventions.

## Evidence

- Source copy: `C:\Users\Innotech\.claude\skills\abp-react-ui`
- Reported issue class: edit forms using `form.reset()` after mount can leave Radix Select controls with stale hidden select state or placeholder text.
- Reported convention drift: pages redeclare local `Field` helpers instead of using the shared component.
