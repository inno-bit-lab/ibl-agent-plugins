---
name: agent-plugin-update
description: 'Update the canonical IBL agent plugin marketplace checkout without requiring the user to remember its folder. Use when a user asks to update, pull, refresh, or sync IBL agent plugins, the ibl-agent-plugins repository, Codex marketplace snapshots, Claude Code, Antigravity, or OpenCode installs from GitHub.'
---

# IBL Agent Plugin Update

Use this skill when the user wants the latest IBL plugins or says they do not
remember where the marketplace repository was cloned.

This skill does not install plugins by default. It updates the canonical GitHub
checkout and, only when requested, refreshes Codex marketplace snapshots.

## Source Of Truth

The canonical repository is:

```text
inno-bit-lab/ibl-agent-plugins
```

Prefer the helper script over asking the user to remember a path:

```powershell
python scripts/update_agent_plugins.py --validate
```

The helper discovers the checkout from:

1. `IBL_AGENT_PLUGINS_HOME`
2. The current working directory and its parents
3. Common team checkout paths such as
   `$env:USERPROFILE\agent-marketplaces\ibl-agent-plugins`
4. Linked plugin installs for Antigravity, Claude Code, and OpenCode

If discovery fails, ask the user to clone the repository once, then rerun the
helper:

```powershell
gh repo clone inno-bit-lab/ibl-agent-plugins "$env:USERPROFILE\agent-marketplaces\ibl-agent-plugins"
```

## Normal Update

When the user asks to update IBL plugins from GitHub:

1. Run:

```powershell
python scripts/update_agent_plugins.py --validate
```

2. Report:
   - discovered repository path
   - branch and before/after commit
   - whether validation passed
   - whether host restarts or reinstall steps are needed

If the repository has uncommitted changes, stop and report them. Do not stash,
discard, reset, or overwrite changes unless the user explicitly asks.

## Codex Marketplace Snapshot

If the user installed the marketplace with:

```powershell
codex plugin marketplace add inno-bit-lab/ibl-agent-plugins --ref main
```

then the Git checkout used by Codex is managed by Codex. Refresh it with:

```powershell
python scripts/update_agent_plugins.py --codex-marketplace-upgrade
```

Use `--validate` as well when a local checkout was discovered and should be
checked after pull:

```powershell
python scripts/update_agent_plugins.py --validate --codex-marketplace-upgrade
```

## Linked Or Copied Installs

For Antigravity or Claude Code installs created with link/junction strategy,
`git pull` is enough to update the files. The host may need a restart or the
workspace may need to be reopened.

For copied installs, pulling the repository does not update the installed copy.
After the pull, rerun the install helper with the same host/scope and
`--strategy copy --force`.

## Safety Rules

- Never run `git reset`, `git checkout --`, or destructive cleanup.
- Never edit installed copies as source of truth.
- Prefer `git pull --ff-only` so local divergent history is surfaced instead of
  being merged silently.
- Treat Codex marketplace refresh as separate from local repository pull.
