# Skill Improvement Inbox

This directory is the shared project base for skill improvement artifacts.

When an agent or a user discovers that a skill produced a wrong, incomplete,
or fragile result, the agent should not patch an installed copy directly. It
should create an improvement artifact under `improvements/inbox`.

## Folder layout

```text
improvements/
├── inbox/       # new improvement artifacts waiting for review/application
├── applied/     # artifacts that were applied to canonical plugin sources
├── rejected/    # artifacts that were reviewed and intentionally not applied
└── _template/   # canonical artifact shape
```

## Artifact layout

Each artifact is a folder:

```text
improvements/inbox/YYYYMMDD-HHMMSS-agent-skill-short-problem/
├── problem.md
├── improvement.md
├── modified-resources.md
├── validation.md
├── candidate/
└── attachments/
```

Required files:

- `problem.md` - what happened, evidence, expected behavior, affected skill.
- `improvement.md` - how the skill/resource should change and why.
- `modified-resources.md` - exact canonical repo paths that should change.
- `validation.md` - checks already run and checks still required.

Optional folders:

- `candidate/` - improved versions of modified files, preserving repo-relative paths.
- `attachments/` - logs, screenshots, command output, or sample inputs.

## Rule

The canonical source is always `plugins/<plugin>/skills/...`. Installed copies
in Claude Code, Codex, Antigravity, or OpenCode are outputs, not authoring
locations.
