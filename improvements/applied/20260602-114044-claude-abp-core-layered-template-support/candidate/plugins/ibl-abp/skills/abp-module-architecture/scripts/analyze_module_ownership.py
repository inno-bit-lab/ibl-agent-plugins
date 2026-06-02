#!/usr/bin/env python3
"""Inventory likely ABP module ownership for backend and React resources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ABP_CORE_SCRIPTS = str(Path(__file__).resolve().parents[2] / "abp-core" / "scripts")
if _ABP_CORE_SCRIPTS not in sys.path:
    sys.path.insert(0, _ABP_CORE_SCRIPTS)

try:
    from abp_context import detect_abp_project  # noqa: E402
except ImportError:  # pragma: no cover - keep the tool usable standalone
    detect_abp_project = None


IGNORED_PARTS = {"bin", "obj", "node_modules", "dist", ".git", ".playwright-mcp", "Properties"}

# Backend resource globs differ by template. nolayers keeps everything in one
# project under concern-named folders; layered fans the same concerns out across
# *.Domain / *.Application(.Contracts) / *.MongoDB projects. The inventory stays
# meaningful on both by selecting the right pattern set.
BACKEND_GLOBS = {
    "nolayers": {
        "entities": ("Entities/**/*.cs",),
        "services": ("Services/**/*.cs",),
        "permissions": ("Permissions/**/*.cs",),
        "localization": ("Localization/**/*.json",),
        "error_codes": ("*DomainErrorCodes.cs",),
        "mongo": ("Data/**/*MongoDbContext*.cs", "Data/**/*IndexInitializer.cs"),
    },
    "layered": {
        # In layered, "entities" captures the whole Domain layer (entities, repo
        # interfaces, domain services) — the bounded context's heart.
        "entities": ("*.Domain/**/*.cs",),
        "services": ("*.Application/**/*AppService*.cs",
                     "*.Application.Contracts/**/I*AppService.cs"),
        "permissions": ("*.Application.Contracts/**/Permissions/**/*.cs",
                        "*.Domain.Shared/**/*Permissions*.cs"),
        "localization": ("*.Domain.Shared/**/Localization/**/*.json",),
        "error_codes": ("*.Domain.Shared/**/*DomainErrorCodes.cs",),
        "mongo": ("*.MongoDB/**/*MongoDbContext*.cs", "*.MongoDB/**/*IndexInitializer.cs"),
    },
}


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


def collect_backend_area(area_root: Path, base: Path,
                         template: str = "nolayers") -> dict[str, list[str]]:
    globs = BACKEND_GLOBS.get(template, BACKEND_GLOBS["nolayers"])
    return {
        concern: [rel(p, base) for p in iter_files(area_root, patterns)]
        for concern, patterns in globs.items()
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


def _host_domain_folders(host_area: Path, base: Path, layered: bool) -> dict[str, list[str]]:
    """Aggregate folders living in the app's own backend — candidates to review
    when deciding what should move into a bounded-context module."""
    possible: dict[str, list[str]] = {}
    if layered:
        roots = list(host_area.glob("*.Domain"))
    else:
        roots = [host_area / "Entities", host_area / "Services"]
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if (child.is_dir() and not (set(child.parts) & IGNORED_PARTS)
                    and any(child.rglob("*.cs"))):
                possible.setdefault(child.name, []).append(rel(str(child), base))
    return possible


def _module_template(module_dir: Path, default: str) -> str:
    """A module may itself be layered (its own *.Domain/*.Application projects)
    or flat. Detect so its inventory uses the right glob set."""
    if any(module_dir.glob("*.Domain")) or any(module_dir.glob("*/*.Domain")):
        return "layered"
    return default


def collect(solution: Path) -> dict[str, object]:
    solution = solution.resolve()

    template = "nolayers"
    if detect_abp_project is not None:
        try:
            template = detect_abp_project(str(solution)).template_type or "nolayers"
        except Exception:
            template = "nolayers"
    layered = template in ("layered", "microservice")
    modules_dir = solution / "modules"

    report: dict[str, object] = {
        "solution": str(solution),
        "template": template,
        "host": {},
        "modules": {},
        "react_host": {},
        "possible_host_domain_folders": {},
    }

    # The app's own backend "area": in layered it's the src/ tree (all layer
    # projects scanned together); in nolayers it's the single host project.
    if layered:
        host_area = solution / "src" if (solution / "src").is_dir() else solution
    else:
        host_area = infer_host_project(solution)

    if host_area:
        report["host"] = collect_backend_area(host_area, solution, template)
        react_host = solution / "react"
        if react_host.exists():
            report["react_host"] = collect_react_area(react_host, solution)
        report["possible_host_domain_folders"] = _host_domain_folders(
            host_area, solution, layered)

    modules: dict[str, object] = {}
    if modules_dir.exists():
        for module_dir in sorted(p for p in modules_dir.iterdir() if p.is_dir()):
            module_report: dict[str, object] = {"backend": {}, "react": {}}
            if any(module_dir.rglob("*.csproj")):
                module_report["backend"] = collect_backend_area(
                    module_dir, solution, _module_template(module_dir, template))
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
