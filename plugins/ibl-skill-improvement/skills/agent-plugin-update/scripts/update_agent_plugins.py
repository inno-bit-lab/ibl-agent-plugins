from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_NAME = "ibl-agent-lugins"
GITHUB_REPO = "inno-bit-lab/ibl-agent-lugins"
PLUGIN_NAMES = ("ibl-abp", "ibl-skill-improvement")


def format_command(command: list[str]) -> str:
    parts: list[str] = []
    for part in command:
        if any(char.isspace() for char in part):
            parts.append(f'"{part}"')
        else:
            parts.append(part)
    return " ".join(parts)


def run(command: list[str], *, cwd: Path | None = None, check: bool = True, dry_run: bool = False) -> str:
    prefix = f"$ {format_command(command)}"
    if cwd is not None:
        prefix += f"  # cwd: {cwd}"
    print(prefix)

    if dry_run:
        return ""

    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = completed.stdout or ""
    if output:
        print(output.rstrip())

    if check and completed.returncode != 0:
        raise SystemExit(f"command failed with exit code {completed.returncode}: {format_command(command)}")
    return output


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def has_repo_markers(path: Path) -> bool:
    return (
        (path / "plugins").is_dir()
        and (path / "improvements").is_dir()
        and (path / "AGENTS.md").is_file()
    )


def git_top_level(path: Path) -> Path | None:
    if not path.exists():
        return None
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        return None
    root = Path(completed.stdout.strip()).resolve()
    if has_repo_markers(root):
        return root
    return None


def marker_ancestor(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if has_repo_markers(candidate):
            return candidate.resolve()
    return None


def add_candidate(candidates: list[Path], seen: set[Path], path: Path) -> None:
    paths = [path]
    try:
        paths.append(Path(os.path.realpath(path)))
    except OSError:
        pass

    for candidate in paths:
        root = git_top_level(candidate) or marker_ancestor(candidate)
        if root is None or root in seen:
            continue
        seen.add(root)
        candidates.append(root)


def common_checkout_paths() -> list[Path]:
    home = Path.home()
    paths = [
        home / "agent-marketplaces" / "ibl-agent-lugins",
        home / "agent-marketplaces" / "ibl-agent-plugins",
        home / "source" / "repos" / "ibl-agent-lugins",
        home / "src" / "ibl-agent-lugins",
    ]

    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        base = Path(userprofile)
        paths.extend([
            base / "agent-marketplaces" / "ibl-agent-lugins",
            base / "agent-marketplaces" / "ibl-agent-plugins",
        ])
    return paths


def installed_plugin_paths() -> list[Path]:
    home = Path.home()
    paths: list[Path] = []

    plugin_bases = [
        home / ".gemini" / "config" / "plugins",
        home / ".claude" / "plugins",
    ]
    for base in plugin_bases:
        for plugin in PLUGIN_NAMES:
            paths.append(base / plugin)

    opencode_skills = home / ".config" / "opencode" / "skills"
    for skill in ("agent-plugin-update", "skill-improvement", "abp-core", "abp-react-ui"):
        paths.append(opencode_skills / skill)

    cwd = Path.cwd()
    for ancestor in (cwd, *cwd.parents):
        for plugin_dir in (ancestor / ".agents" / "plugins", ancestor / "_agents" / "plugins", ancestor / "plugins"):
            for plugin in PLUGIN_NAMES:
                paths.append(plugin_dir / plugin)
    return paths


def discover_repo(explicit_repo: str | None) -> Path:
    candidates: list[Path] = []
    seen: set[Path] = set()

    if explicit_repo:
        explicit = expand_path(explicit_repo)
        root = git_top_level(explicit) or marker_ancestor(explicit)
        if root is None or git_top_level(root) is None:
            raise SystemExit(f"not an IBL agent plugins Git checkout: {explicit}")
        return root

    env_repo = os.environ.get("IBL_AGENT_PLUGINS_HOME")
    if env_repo:
        add_candidate(candidates, seen, expand_path(env_repo))

    add_candidate(candidates, seen, Path(__file__).resolve())

    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        add_candidate(candidates, seen, path)

    for path in common_checkout_paths():
        add_candidate(candidates, seen, path)

    for path in installed_plugin_paths():
        add_candidate(candidates, seen, path)

    for candidate in candidates:
        if git_top_level(candidate) is not None:
            return candidate

    raise SystemExit(
        "No IBL agent plugins Git checkout found.\n"
        "Clone it once with PowerShell:\n"
        f'  gh repo clone {GITHUB_REPO} "$env:USERPROFILE\\agent-marketplaces\\{REPO_NAME}"\n'
        "Or set IBL_AGENT_PLUGINS_HOME to the checkout path."
    )


def ensure_clean(repo: Path, allow_dirty: bool, dry_run: bool) -> None:
    status = run(["git", "-C", str(repo), "status", "--porcelain"], dry_run=dry_run)
    if status.strip() and not allow_dirty:
        raise SystemExit(
            "Repository has uncommitted changes. Commit, stash, or rerun with --allow-dirty "
            "only if you explicitly want git pull to proceed with local changes."
        )


def update_repo(repo: Path, args: argparse.Namespace) -> None:
    branch = run(["git", "-C", str(repo), "branch", "--show-current"], dry_run=args.dry_run).strip() or "detached"
    before = run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], dry_run=args.dry_run).strip()

    print(f"Repository: {repo}")
    print(f"Branch: {branch}")
    if before:
        print(f"Before: {before}")

    if not args.skip_pull:
        ensure_clean(repo, args.allow_dirty, args.dry_run)
        run(["git", "-C", str(repo), "pull", "--ff-only"], dry_run=args.dry_run)

    after = run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], dry_run=args.dry_run).strip()
    if after:
        print(f"After: {after}")


def validate_repo(repo: Path, dry_run: bool) -> None:
    validator = repo / "tools" / "validate-plugin.py"
    if not validator.is_file():
        raise SystemExit(f"missing validator: {validator}")
    run([sys.executable, str(validator)], cwd=repo, dry_run=dry_run)


def codex_marketplace_upgrade(dry_run: bool) -> None:
    if shutil.which("codex") is None:
        raise SystemExit("codex CLI not found; cannot run marketplace upgrade")
    run(["codex", "plugin", "marketplace", "upgrade"], dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update the canonical IBL agent plugins checkout.")
    parser.add_argument("--repo", help="Explicit path to the ibl-agent-lugins checkout.")
    parser.add_argument("--validate", action="store_true", help="Run tools/validate-plugin.py after update.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow git pull when the checkout has local changes.")
    parser.add_argument("--skip-pull", action="store_true", help="Skip git pull and only run requested extra actions.")
    parser.add_argument("--codex-marketplace-upgrade", action="store_true", help="Run codex plugin marketplace upgrade.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    args = parser.parse_args()

    repo = discover_repo(args.repo)
    update_repo(repo, args)

    if args.validate:
        validate_repo(repo, args.dry_run)

    if args.codex_marketplace_upgrade:
        codex_marketplace_upgrade(args.dry_run)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
