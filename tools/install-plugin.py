from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def copytree(src: Path, dst: Path, force: bool) -> None:
    if dst.exists():
        if not force:
            raise SystemExit(f"{dst} already exists; pass --force to replace it")
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    shutil.copytree(src, dst)


def link_or_copy(src: Path, dst: Path, strategy: str, force: bool) -> None:
    if strategy == "copy":
        copytree(src, dst, force)
        return

    if dst.exists() or dst.is_symlink():
        if not force:
            raise SystemExit(f"{dst} already exists; pass --force to replace it")
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)

    try:
        os.symlink(src, dst, target_is_directory=True)
    except OSError:
        if os.name == "nt":
            import subprocess

            subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], check=True)
        else:
            raise


def install_opencode(args: argparse.Namespace) -> None:
    if args.scope == "workspace":
        base = Path(args.workspace or Path.cwd()) / ".opencode" / "skills"
    else:
        base = Path.home() / ".config" / "opencode" / "skills"
    base.mkdir(parents=True, exist_ok=True)
    for skill in sorted(args.skills_path.iterdir()):
        if skill.is_dir():
            link_or_copy(skill, base / skill.name, args.strategy, args.force)
            print(f"installed {skill.name} -> {base / skill.name}")


def install_antigravity(args: argparse.Namespace) -> None:
    if args.scope == "workspace":
        base = Path(args.workspace or Path.cwd()) / ".agents" / "plugins"
    else:
        base = Path.home() / ".gemini" / "config" / "plugins"
    base.mkdir(parents=True, exist_ok=True)
    link_or_copy(args.plugin_path, base / args.plugin_name, args.strategy, args.force)
    print(f"installed {args.plugin_name} -> {base / args.plugin_name}")


def install_codex(args: argparse.Namespace) -> None:
    if args.scope == "workspace":
        workspace = Path(args.workspace or ROOT)
        plugin_base = workspace / "plugins"
        marketplace = workspace / ".agents" / "plugins" / "marketplace.json"
    else:
        plugin_base = Path.home() / "plugins"
        marketplace = Path.home() / ".agents" / "plugins" / "marketplace.json"
    plugin_base.mkdir(parents=True, exist_ok=True)
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    target = plugin_base / args.plugin_name
    if target.resolve() != args.plugin_path.resolve():
        link_or_copy(args.plugin_path, target, args.strategy, args.force)

    if marketplace.is_file():
        data = json.loads(marketplace.read_text(encoding="utf-8"))
    else:
        if args.scope == "workspace":
            data = {"name": "ibl-agent-plugins", "interface": {"displayName": "IBL Agent Plugins"}, "plugins": []}
        else:
            data = {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}

    plugins = data.setdefault("plugins", [])
    plugins[:] = [p for p in plugins if p.get("name") != args.plugin_name]
    plugins.append({
        "name": args.plugin_name,
        "source": {"source": "local", "path": f"./plugins/{args.plugin_name}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    })
    marketplace.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"installed {args.plugin_name} -> {target}")
    print(f"updated {marketplace}")


def install_claude(args: argparse.Namespace) -> None:
    if args.scope == "workspace":
        base = Path(args.workspace or ROOT) / "plugins"
    else:
        base = Path.home() / ".claude" / "plugins"
    base.mkdir(parents=True, exist_ok=True)
    target = base / args.plugin_name
    if target.resolve() != args.plugin_path.resolve():
        link_or_copy(args.plugin_path, target, args.strategy, args.force)
    print(f"installed {args.plugin_name} -> {target}")
    if args.scope == "workspace":
        print(f"use marketplace manifest: {Path(args.workspace or ROOT) / '.claude-plugin' / 'marketplace.json'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a local IBL agent plugin into a selected host.")
    parser.add_argument("host", choices=["claude", "codex", "antigravity", "opencode"])
    parser.add_argument("--plugin", default="ibl-abp", help="Plugin folder name under plugins/.")
    parser.add_argument("--scope", choices=["workspace", "global"], default="workspace")
    parser.add_argument("--workspace", help="Workspace path for workspace-scoped installs.")
    parser.add_argument("--strategy", choices=["link", "copy"], default="link")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.plugin_name = args.plugin
    args.plugin_path = ROOT / "plugins" / args.plugin_name
    args.skills_path = args.plugin_path / "skills"

    if not args.plugin_path.is_dir() or not args.skills_path.is_dir():
        raise SystemExit(f"Plugin not found or missing skills/: {args.plugin_path}")

    installers = {
        "claude": install_claude,
        "codex": install_codex,
        "antigravity": install_antigravity,
        "opencode": install_opencode,
    }
    installers[args.host](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
