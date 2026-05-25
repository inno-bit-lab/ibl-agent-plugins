"""
validate_module.py — Validate an ABP *Module.cs file.

Checks:
  - inherits from AbpModule
  - has [DependsOn(...)] attribute (warning if missing — not always required)
  - overrides ConfigureServices (warning if missing — sometimes intentional)
  - does NOT register middleware via OnApplicationInitialization unless it's the
    host module (heuristic: file path ends with /Host/ or has "Web" in name)

Usage:
  python validate_module.py --module-path src/MyProject/MyProjectModule.cs
  python validate_module.py            # prompts for path
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Finding:
    level: str  # "error" | "warning" | "info"
    message: str


def _prompt_path() -> str:
    try:
        return input("Module file path (e.g. src/MyProject/MyProjectModule.cs): ").strip()
    except EOFError:
        return ""


def validate(module_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not module_path.is_file():
        findings.append(Finding("error", f"File not found: {module_path}"))
        return findings

    text = module_path.read_text(encoding="utf-8", errors="ignore")

    if not re.search(r"class\s+\w+Module\s*:\s*(?:[\w<>]+,\s*)*AbpModule\b", text):
        findings.append(
            Finding(
                "error",
                "Module class must inherit from AbpModule (no match for ': AbpModule').",
            )
        )

    if not re.search(r"\[DependsOn\s*\(", text):
        findings.append(
            Finding(
                "warning",
                "No [DependsOn(...)] attribute found. Most ABP modules depend on at "
                "least AbpDddDomainModule or AbpAspNetCoreMvcModule — confirm this is "
                "intentional.",
            )
        )

    if not re.search(r"override\s+void\s+ConfigureServices", text):
        findings.append(
            Finding(
                "info",
                "No ConfigureServices override. Fine if the module is a pure "
                "DependsOn aggregator, otherwise add it.",
            )
        )

    # A module is "the host" if its name suggests it (Host/Web suffix) OR if it's
    # the only module in its parent folder structure (nolayers single-project).
    stem = module_path.stem
    parent = module_path.parent
    siblings_with_dots = [
        p for p in parent.parent.iterdir() if p.is_dir() and "." in p.name
    ] if parent.parent.exists() else []
    is_host_module = (
        "/Host/" in module_path.as_posix()
        or stem.endswith("HostModule")
        or stem.endswith("WebModule")
        or stem.endswith("ApiModule")
        # Single-project (nolayers) — no sibling .Domain/.Application/etc folders
        or not any(
            s.name.endswith((".Domain", ".Application", ".HttpApi", ".Web", ".Host"))
            for s in siblings_with_dots
        )
    )
    if not is_host_module and re.search(
        r"override\s+void\s+OnApplicationInitialization", text
    ):
        findings.append(
            Finding(
                "warning",
                "OnApplicationInitialization (middleware setup) found in a non-host "
                "module. Middleware should live in the final host application only.",
            )
        )

    # Anti-pattern: AddScoped / AddTransient / AddSingleton with concrete class
    if re.search(r"\.AddScoped\s*<", text) or re.search(r"\.AddTransient\s*<", text):
        findings.append(
            Finding(
                "info",
                "Manual AddScoped/AddTransient calls detected. Prefer the "
                "ITransientDependency / IScopedDependency marker interfaces for "
                "auto-registration unless you have a specific reason.",
            )
        )

    # Anti-pattern: DateTime.Now / DateTime.UtcNow usage in a module is rare,
    # but worth flagging if it appears.
    if re.search(r"\bDateTime\.(Now|UtcNow)\b", text):
        findings.append(
            Finding(
                "warning",
                "DateTime.Now/UtcNow used directly. Inject IClock or use the "
                "Clock property on ABP base classes for testability and timezone "
                "correctness.",
            )
        )

    if not findings:
        findings.append(Finding("info", "Module looks healthy."))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an ABP *Module.cs file")
    parser.add_argument("--module-path", help="Path to the *Module.cs file")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress info-level findings (errors/warnings only)",
    )
    args = parser.parse_args()

    path_str = args.module_path or _prompt_path()
    if not path_str:
        print("No module path provided.", file=sys.stderr)
        return 2

    findings = validate(Path(path_str))
    exit_code = 0
    icons = {"error": "[X]", "warning": "[!]", "info": "[i]"}
    for f in findings:
        if args.quiet and f.level == "info":
            continue
        print(f"{icons.get(f.level, '?')} {f.level.upper()}: {f.message}")
        if f.level == "error":
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
