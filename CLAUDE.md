# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is **not an application** — it is the canonical GitHub source (`inno-bit-lab/ibl-agent-plugins`) for IBL's reusable AI-agent plugins and skills. The "code" is mostly Markdown skill content, Python helper scripts, and thin JSON manifests that adapt the same skills to four hosts: **Codex, Claude Code, Antigravity, and OpenCode**. There is no build system, no test framework, and no application to run.

Repo-wide agent rules live in [AGENTS.md](AGENTS.md). CLAUDE.md complements it with architecture and commands; read AGENTS.md too rather than relying on this file alone.

## Core invariant: skill content lives exactly once

Skill text exists in **one** place only:

```
plugins/<plugin>/skills/<skill>/SKILL.md   (+ references/, scripts/, templates/)
```

Everything else is an adapter or a generated copy:

- The three per-plugin manifests are **thin adapters**, not content. Never duplicate skill prose into them or into marketplace files:
  - `.claude-plugin/plugin.json` (Claude Code)
  - `.codex-plugin/plugin.json` (Codex — also carries `interface.defaultPrompt`)
  - `plugin.json` (Antigravity)
- Installed copies under `~/.claude`, `~/.codex`, `~/.config/opencode`, `~/.gemini/config/plugins`, or a workspace's `.agents/plugins` are **outputs**. Never edit them as a source of truth, and never edit them at all unless the user explicitly asks to install/sync. OpenCode consumes the `skills/<skill>` folders directly via link/copy.

There are two plugins: `ibl-abp` (7 ABP-framework skills) and `ibl-skill-improvement` (2 meta-skills for evolving the skills themselves).

## Commands

Run everything from the repo root. The environment is Windows / PowerShell.

```powershell
# Full structural validation — run after ANY manifest, skill, or improvement change
python tools/validate-plugin.py

# Compile-check a Python script you changed inside a skill or tools/
python -m py_compile path\to\script.py

# Install a plugin locally into a host (development / sync only)
python tools/install-plugin.py claude      --plugin ibl-abp --scope workspace
python tools/install-plugin.py codex       --plugin ibl-abp --scope workspace
python tools/install-plugin.py antigravity --plugin ibl-abp --scope workspace --workspace C:\path\to\project --strategy link
python tools/install-plugin.py opencode    --plugin ibl-abp --scope global    --strategy link

# Improvement inbox lifecycle (see "Improvement workflow" below)
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py list
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py validate improvements/inbox/<artifact-id>
python plugins/ibl-skill-improvement/skills/skill-improvement/scripts/improvement_inbox.py publish  improvements/inbox/<artifact-id> --create-pr

# Update the canonical checkout (git pull --ff-only, then validate)
python plugins/ibl-skill-improvement/skills/agent-plugin-update/scripts/update_agent_plugins.py --validate
```

Always remove generated `__pycache__/` folders and `.pyc` files before finishing a change (they are gitignored, but don't leave them behind).

## What `tools/validate-plugin.py` enforces

This script is the de-facto CI gate. It checks, and will exit non-zero on:

- All marketplace and per-plugin manifests are present and valid JSON.
- Each Codex manifest's `name` matches its folder, `skills` is `"./skills/"`, and `interface.defaultPrompt` is a list of **at most 3** entries.
- Every `SKILL.md` has YAML frontmatter whose `name` **exactly matches the skill folder name**, and a non-empty `description` of **≤ 1024 chars** (the Agent Skills discovery limit).
- No file under `plugins/` hardcodes a global skill path (`~/.claude/skills`, etc.).
- The `improvements/{inbox,applied,rejected,_template}` structure exists.

**`PLUGIN_SKILLS` in `tools/validate-plugin.py` is the authoritative skill registry.** When you add, remove, or rename a skill, update that dict — otherwise validation fails with "missing expected skills" or warns about "unexpected skill directories".

## Skill authoring conventions

- `SKILL.md` frontmatter holds **only** `name` and `description` (valid YAML). The `description` is what agents match against for discovery — keep it dense with trigger keywords but within the 1024-char limit.
- Put detailed, not-always-needed knowledge in `references/*.md` (progressive disclosure); keep `SKILL.md` as the always-loaded overview. Prefer growing `references/` over bloating `SKILL.md`.
- Prefer a `scripts/*.py` helper for any deterministic, repeatable action over describing the steps in prose.
- Use repo-relative or placeholder paths (e.g. `<skills-root>/...`), never machine-specific absolute paths.

### The `abp-core` shared context module

`plugins/ibl-abp/skills/abp-core/scripts/abp_context.py` is imported by the other `abp-*` skills to detect the target ABP project (name, root namespace, template type, data provider, paths) and to resolve template placeholders. When generating ABP code, skills expand placeholders such as `{{PROJECT_NAME}}`, `{{ROOT_NAMESPACE}}`, `{{TEMPLATE_TYPE}}`, `{{DATA_PROVIDER}}`, `{{PROJECT_ROOT}}`, `{{SOLUTION_ROOT}}` via this module. Changing its API or placeholder set affects every other ABP skill — treat it as shared infrastructure. `abp-core` is the entry-point skill that delegates to `abp-feature-dev`, `abp-module-architecture`, `abp-mongodb`, `abp-multitenancy`, `abp-react-ui`, and `abp-testing`.

## Improvement workflow (how skills evolve)

When a skill produces a wrong/incomplete result or the user gives reusable feedback, do **not** silently patch a skill — record a versioned artifact. This is the repository's central process; full rules are in [AGENTS.md](AGENTS.md) and `improvements/README.md`.

- **Capture Mode** — create `improvements/inbox/<id>/` with `problem.md`, `improvement.md`, `modified-resources.md`, `validation.md` (and optional `candidate/` files preserving repo-relative paths, optional `attachments/`). Publish it as a **proposal-only** branch/PR containing *only* that artifact folder. Do **not** touch `plugins/` in Capture Mode unless the user explicitly asks to process it now.
- **Process Mode** — read the artifact, apply the minimal correct patch to canonical paths under `plugins/`, run validation, then move the artifact to `improvements/applied/` (or `improvements/rejected/` with a note in `validation.md`). Keep applied artifacts as audit history.

The repo root used as the improvement base must contain both `plugins/` and `improvements/`. When a skill runs from an installed cache, that cache is **not** the base — the helper scripts discover the canonical checkout (current dir → `%USERPROFILE%\agent-marketplaces\ibl-agent-plugins` → linked installs → optional `IBL_AGENT_PLUGINS_HOME`); if discovery fails, ask the user to `gh repo clone` rather than writing into the cache.
