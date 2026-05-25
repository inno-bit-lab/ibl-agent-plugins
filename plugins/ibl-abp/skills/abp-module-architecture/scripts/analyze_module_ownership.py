#!/usr/bin/env python3
"""Inventory likely ABP module ownership for backend and React resources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


IGNORED_PARTS = {"bin", "obj", "node_modules", "dist", ".git", ".playwright-mcp"}


def iter_files(root: Path, patterns: tuple[str, ...]) -> list[str]:
    if not root.exists():
        return []
    found: list[str] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            if path.is_file() and not (set(path.parts) & IGNORED_PARTS):
                found.append(str(path))
    return sorted(found)


def rel(path: str, base: Path) -> str:
    try:
        return str(Path(path).relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def collect_backend_area(area_root: Path, base: Path) -> dict[str, list[str]]:
    return {
        "entities": [rel(p, base) for p in iter_files(area_root, ("Entities/**/*.cs",))],
        "services": [rel(p, base) for p in iter_files(area_root, ("Services/**/*.cs",))],
        "permissions": [rel(p, base) for p in iter_files(area_root, ("Permissions/**/*.cs",))],
        "localization": [rel(p, base) for p in iter_files(area_root, ("Localization/**/*.json",))],
        "error_codes": [
            rel(p, base)
            for p in iter_files(area_root, ("*DomainErrorCodes.cs",))
        ],
        "mongo": [
            rel(p, base)
            for p in iter_files(area_root, ("Data/**/*MongoDbContext*.cs", "Data/**/*IndexInitializer.cs"))
        ],
    }


def collect_react_area(area_root: Path, base: Path) -> dict[str, list[str]]:
    src = area_root / "src"
    return {
        "pages": [rel(p, base) for p in iter_files(src / "pages", ("*.ts", "*.tsx"))],
        "components": [rel(p, base) for p in iter_files(src / "components", ("*.ts", "*.tsx"))],
        "api": [rel(p, base) for p in iter_files(src / "lib" / "api", ("*.ts", "*.tsx"))],
        "module": [rel(p, base) for p in iter_files(src, ("module.ts", "module.tsx"))],
    }


def infer_host_project(solution: Path) -> Path | None:
    candidates = [
        path
        for path in solution.iterdir()
        if path.is_dir()
        and (path / f"{path.name}.csproj").exists()
        and path.name.lower() not in {"test", "tests", "react"}
    ]
    return candidates[0] if candidates else None


def collect(solution: Path) -> dict[str, object]:
    solution = solution.resolve()
    host = infer_host_project(solution)
    modules_dir = solution / "modules"

    report: dict[str, object] = {
        "solution": str(solution),
        "host": {},
        "modules": {},
        "react_host": {},
        "possible_host_domain_folders": {},
    }

    if host:
        report["host"] = collect_backend_area(host, solution)
        react_host = solution / "react"
        if react_host.exists():
            report["react_host"] = collect_react_area(react_host, solution)

        possible: dict[str, list[str]] = {}
        for folder in (host / "Entities", host / "Services"):
            if folder.exists():
                for child in folder.iterdir():
                    if child.is_dir() and any(child.rglob("*.cs")):
                        possible.setdefault(child.name, []).append(rel(str(child), solution))
        report["possible_host_domain_folders"] = possible

    modules: dict[str, object] = {}
    if modules_dir.exists():
        for module_dir in sorted(p for p in modules_dir.iterdir() if p.is_dir()):
            module_report: dict[str, object] = {"backend": {}, "react": {}}
            csproj_dirs = [
                p for p in module_dir.iterdir()
                if p.is_dir() and any(p.glob("*.csproj"))
            ]
            if csproj_dirs:
                module_report["backend"] = collect_backend_area(module_dir, solution)
            react_dir = module_dir / "react"
            if react_dir.exists():
                module_report["react"] = collect_react_area(react_dir, solution)
            modules[module_dir.name] = module_report
    report["modules"] = modules

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solution", default=".", help="ABP solution root")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    report = collect(Path(args.solution))
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(json.dumps(report, indent=2))
    possible = report.get("possible_host_domain_folders") or {}
    if possible:
        print("\nPossible host-owned domain folders to review:")
        for name, paths in possible.items():
            print(f"- {name}: {', '.join(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
