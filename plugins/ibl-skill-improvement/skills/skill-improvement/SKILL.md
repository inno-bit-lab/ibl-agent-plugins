---
name: skill-improvement
description: 'Capture, review, and apply reusable improvements to IBL agent skills. Use when a user says a skill failed, asks to auto-improve a skill, wants to record an improvement artifact, process improvements/inbox, apply a candidate skill version, validate skill improvement artifacts, or propagate a skill fix through the canonical plugin repository instead of editing installed agent copies.'
---

# IBL Skill Improvement

Use this skill to turn runtime failures into reusable skill improvements.

The repository root is the improvement base. It must contain both:

- `plugins/`
- `improvements/`

Never edit installed copies in Claude Code, Codex, Antigravity, or OpenCode as
the source of truth. Apply changes to canonical paths under `plugins/`.

When this skill is running from an installed plugin cache, that cache is not the
improvement base. Codex, Claude Code, Antigravity, and OpenCode do not set
`IBL_AGENT_PLUGINS_HOME` automatically when installing from a marketplace.

Use the helper script next to this `SKILL.md`; it discovers the canonical
repository from:

1. `IBL_AGENT_PLUGINS_HOME`, only if the user or team explicitly configured it
2. The current working directory and its parents
3. `$env:USERPROFILE\agent-marketplaces\ibl-agent-lugins`
4. Linked plugin installs for Antigravity, Claude Code, and OpenCode

If discovery fails, do not write into the installed cache. Ask the user to clone
the repository once:

```powershell
gh repo clone inno-bit-lab/ibl-agent-lugins "$env:USERPROFILE\agent-marketplaces\ibl-agent-lugins"
```

For non-standard locations, pass `--repo` to the helper subcommand or ask the
user to define `IBL_AGENT_PLUGINS_HOME` persistently:

```powershell
python <this-skill-folder>\scripts\improvement_inbox.py list --repo C:\path\to\ibl-agent-lugins
```

## Two Modes

### Capture Mode

Use when the user says a skill failed and asks to improve it.

1. Identify the affected skill and plugin from the conversation and touched files.
2. Create a new folder under `improvements/inbox/`.
3. Fill the required files:
   - `problem.md`
   - `improvement.md`
   - `modified-resources.md`
   - `validation.md`
4. If you already know the fix, add improved file copies under `candidate/`,
   preserving repo-relative paths.
5. Do not apply the fix silently unless the user explicitly asked to apply it
   now.
6. Validate the artifact.
7. Unless the user explicitly asked for a local-only draft, publish the proposal
   as a branch and PR that contains only `improvements/inbox/<artifact-id>/`.
   Do not modify canonical `plugins/` paths in Capture Mode.

Prefer the helper:

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py new `
  --skill abp-feature-dev `
  --plugin ibl-abp `
  --agent codex `
  --problem "The scaffold generated the wrong namespace" `
  --improvement "Clarify namespace resolution and update scaffold_entity.py" `
  --resource "plugins/ibl-abp/skills/abp-feature-dev/scripts/scaffold_entity.py"
```

If the skill is installed in an agent cache, run the same script from the
installed skill folder instead of assuming the current workspace is this repo.

After creating the artifact, validate and publish it:

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py validate improvements/inbox/<artifact-id>
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py publish improvements/inbox/<artifact-id> --create-pr
```

The `publish` command creates `improvement/<artifact-id>`, commits only the
artifact folder, pushes the branch, and opens a proposal-only PR when `gh` is
available. If there are unrelated dirty files, stop and report them instead of
mixing them into the proposal.

### Process Mode

Use when the user asks to work the inbox, apply an improvement, or review a
specific artifact.

1. List pending artifacts:

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py list
```

2. Validate the selected artifact:

```powershell
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py validate improvements/inbox/<artifact-id>
```

3. Read `problem.md`, `improvement.md`, `modified-resources.md`, and
   `validation.md`.
4. Inspect any `candidate/` files. Treat them as proposed replacements, not as
   automatically trusted output.
5. Apply the minimal correct patch to canonical repo paths under `plugins/`.
6. Run relevant validation:
   - `python tools/validate-plugin.py`
   - `python <plugin-creator>/scripts/validate_plugin.py plugins/<plugin>`
   - `python -m py_compile` for modified Python scripts
   - any regression command named in `validation.md`
7. Move the artifact to `improvements/applied/` only after validation passes.
   Move to `improvements/rejected/` if the improvement is invalid, unsafe, or
   obsolete, and add a short rejection note to `validation.md`.

## Artifact Contract

Each improvement folder must contain:

```text
problem.md
improvement.md
modified-resources.md
validation.md
candidate/
attachments/
```

`modified-resources.md` must name canonical repo paths, for example:

```markdown
- `plugins/ibl-abp/skills/abp-feature-dev/SKILL.md`
- `plugins/ibl-abp/skills/abp-feature-dev/scripts/scaffold_entity.py`
```

If candidate files are present, they must preserve repo-relative paths:

```text
candidate/plugins/ibl-abp/skills/abp-feature-dev/SKILL.md
```

## Review Rules

- Prefer improving references or scripts over bloating `SKILL.md`.
- Keep frontmatter `description` concise and valid YAML.
- Preserve progressive disclosure: details belong in `references/` when they
  are not always needed.
- Add or update validation evidence when a bug can recur.
- Keep the improvement artifact as audit history after applying it.
- Do not update marketplaces or installed copies unless the user asks for sync.

## Status Language

When finishing, report:

- artifact id
- branch and PR URL for Capture Mode proposals
- files changed
- validation commands run
- whether the artifact remains in `inbox`, moved to `applied`, or moved to
  `rejected`
