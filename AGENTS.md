# Agent Instructions

These instructions apply to the whole repository.

## Repository Purpose

This repository is the canonical GitHub source for IBL agent plugins, skills,
improvement proposals, and host adapters for Codex, Claude Code, Antigravity,
and OpenCode.

## Source Of Truth

- Author skill content only under `plugins/<plugin>/skills/<skill>/`.
- Treat installed copies in agent-specific folders as generated outputs.
- Do not edit global agent folders such as `~/.claude`, `~/.codex`,
  `~/.config/opencode`, `~/.gemini/config/plugins`, or Antigravity workspace
  locations such as `.agents/plugins` unless the user explicitly asks for
  installation or sync.
- Keep plugin manifests as thin adapters. Do not duplicate skill text in
  manifests or marketplace files.

## Plugin Shape

Each plugin should use this layout when applicable:

```text
plugins/<plugin>/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── plugin.json
└── skills/
```

OpenCode consumes `skills/<skill>` folders directly through link/copy. Keep the
same `SKILL.md` source shared across all hosts.

Antigravity 2.0 consumes plugin folders from:

```text
<workspace-root>/.agents/plugins/<plugin-name>/
<workspace-root>/_agents/plugins/<plugin-name>/
~/.gemini/config/plugins/<plugin-name>/
```

Use `tools/install-plugin.py antigravity --plugin <plugin> --scope workspace`
or `--scope global` instead of manually copying plugin folders.

## Improvement Workflow

When a user says a skill failed, asks to improve a skill, or provides feedback
that should become reusable skill knowledge:

1. Identify the affected plugin, skill, and resource.
2. Create an artifact under `improvements/inbox/<id>/`.
3. Include:
   - `problem.md`
   - `improvement.md`
   - `modified-resources.md`
   - `validation.md`
   - optional `candidate/` files preserving repo-relative paths
   - optional `attachments/` with logs or examples
4. Apply changes only to canonical paths under `plugins/`.
5. Validate before moving the artifact to `improvements/applied/`.
6. Move invalid or obsolete artifacts to `improvements/rejected/` and record why.

Use the helper when creating or validating artifacts:

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py list
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py validate improvements/inbox/<artifact-id>
```

## Validation

Run the repo validator after structural, manifest, skill, or improvement changes:

```powershell
python tools/validate-plugin.py
```

For Codex plugin manifests, also run the plugin creator validator when
available:

```powershell
python <plugin-creator>/scripts/validate_plugin.py plugins/<plugin>
```

For Python scripts changed inside skills or tools:

```powershell
python -m py_compile <script.py>
```

Remove generated `__pycache__/` folders and `.pyc` files before finishing.

## Editing Rules

- Keep `SKILL.md` frontmatter valid YAML with only `name` and `description`.
- Keep descriptions concise enough for agent-skill discovery.
- Prefer detailed reusable knowledge in `references/` instead of bloating
  `SKILL.md`.
- Prefer scripts for deterministic repeatable actions.
- Preserve the improvement artifact history as audit evidence.

## GitHub Workflow

For team propagation, use GitHub as the update channel:

1. Create or process an improvement artifact.
2. Patch canonical plugin/skill files.
3. Validate locally.
4. Commit on a branch and open a PR.
5. Merge after review.
6. Agents update by pulling/reinstalling from this repository.
