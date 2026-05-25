"""
abp_context.py — Shared module for ABP skill scripts.

Provides:
  - detect_abp_project(cwd): auto-detect project metadata from .csproj + folders
  - load_or_prompt_config(project_root): load .abp-skills.json or prompt user
  - resolve_placeholders(text, ctx): substitute {{PROJECT_NAME}} etc.

Other abp-* skills import this by adding the abp-core scripts dir to sys.path:

    import sys, os
    sys.path.insert(0, '<skills-root>/abp-core/scripts')
    from abp_context import load_or_prompt_config, resolve_placeholders
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

CONFIG_FILENAME = ".abp-skills.json"


@dataclass
class AbpContext:
    project_name: str = ""
    root_namespace: str = ""
    template_type: str = ""   # nolayers | layered | microservice
    data_provider: str = ""   # mongodb | efcore
    project_root: str = ""    # path to the main src/<Project> folder (relative to solution)
    solution_root: str = ""   # absolute path to solution root

    def as_dict(self) -> dict:
        return asdict(self)


SOLUTION_GLOBS = ("*.sln", "*.slnx", "*.abpsln")


def find_solution_root(start: Path) -> Optional[Path]:
    """Walk upward from `start` to find a folder containing a solution file."""
    cur = start.resolve()
    for parent in [cur, *cur.parents]:
        for pattern in SOLUTION_GLOBS:
            if any(parent.glob(pattern)):
                return parent
    return None


def _project_dirs(solution_root: Path) -> list[Path]:
    """
    Return candidate project folders under `solution_root`.
    Supports both src/<Project>/ (layered/microservice) and <Project>/ (no-src layout).
    """
    src = solution_root / "src"
    if src.is_dir():
        return [p for p in src.iterdir() if p.is_dir() and any(p.glob("*.csproj"))]
    return [
        p
        for p in solution_root.iterdir()
        if p.is_dir() and any(p.glob("*.csproj")) and not p.name.startswith(".")
    ]


def _read_csproj_root_namespace(csproj_path: Path) -> Optional[str]:
    try:
        text = csproj_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r"<RootNamespace>(.*?)</RootNamespace>", text)
    if m:
        return m.group(1).strip()
    # Fallback: assume namespace == csproj file stem
    return csproj_path.stem


def _detect_template_type(solution_root: Path) -> str:
    """
    Heuristic:
      - 'microservice' if multiple .Host projects exist (>=2)
      - 'layered' if .Domain AND .Application projects exist as separate csprojs
      - 'nolayers' otherwise (single project, sometimes with a sibling .Tests)
    """
    candidates = _project_dirs(solution_root)
    csprojs = [c for p in candidates for c in p.glob("*.csproj")]
    # Also scan one level deeper (e.g. src/<Project>/<sub>/*.csproj is unusual but possible)
    names = [c.stem for c in csprojs]

    if sum(1 for n in names if n.endswith(".Host")) >= 2:
        return "microservice"
    if any(n.endswith(".Domain") for n in names) and any(
        n.endswith(".Application") for n in names
    ):
        return "layered"
    return "nolayers"


def _detect_data_provider(solution_root: Path) -> str:
    """
    Tally MongoDB vs EFCore package references across all csprojs and pick the
    majority. ABP module packages come in {ModuleName}.MongoDB or
    {ModuleName}.EntityFrameworkCore variants, so a simple substring count is
    reliable.
    """
    mongo = efcore = 0
    for csproj in solution_root.rglob("*.csproj"):
        try:
            text = csproj.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        mongo += text.count(".MongoDB")
        efcore += text.count(".EntityFrameworkCore")
    if mongo == 0 and efcore == 0:
        return "unknown"
    return "mongodb" if mongo >= efcore else "efcore"


def _detect_main_project(solution_root: Path, template_type: str) -> Optional[Path]:
    """Find the 'main' project folder."""
    candidates = _project_dirs(solution_root)
    if not candidates:
        return None
    # Exclude obvious test projects from main candidates
    non_tests = [c for c in candidates if not c.name.endswith(".Tests")] or candidates
    if template_type == "nolayers":
        # Pick the one whose name has no dot-suffix (e.g. "Ibl360" not "Ibl360.Domain")
        for c in non_tests:
            if "." not in c.name:
                return c
    # Layered/microservice: pick *.Domain or *.Host as anchor; fall back to first
    for c in non_tests:
        if c.name.endswith(".Domain"):
            return c
    return non_tests[0]


def detect_abp_project(cwd: Optional[str] = None) -> AbpContext:
    """
    Auto-detect ABP project metadata.

    Returns an AbpContext with fields filled in where detection succeeded;
    empty strings where it couldn't determine the value.
    """
    start = Path(cwd or os.getcwd())
    ctx = AbpContext()

    sln_root = find_solution_root(start)
    if sln_root is None:
        return ctx

    ctx.solution_root = str(sln_root)
    ctx.template_type = _detect_template_type(sln_root)
    ctx.data_provider = _detect_data_provider(sln_root)

    main = _detect_main_project(sln_root, ctx.template_type)
    if main is not None:
        ctx.project_root = str(main.relative_to(sln_root)).replace("\\", "/")
        # Project name == folder name (drop layer suffix if present)
        ctx.project_name = main.name.split(".")[0]
        csproj = next(iter(main.glob("*.csproj")), None)
        if csproj is not None:
            ns = _read_csproj_root_namespace(csproj)
            ctx.root_namespace = ns or ctx.project_name

    return ctx


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"{label}{suffix}: ").strip()
    except EOFError:
        ans = ""
    return ans or default


def load_or_prompt_config(project_root: Optional[str] = None) -> AbpContext:
    """
    Resolution cascade:
      1. Read .abp-skills.json from solution root (or `project_root` if given).
      2. Fall back to auto-detection.
      3. Prompt the user for any still-empty fields and persist the file.
    """
    start = Path(project_root or os.getcwd())
    detected = detect_abp_project(str(start))
    sln_root = Path(detected.solution_root) if detected.solution_root else start
    config_path = sln_root / CONFIG_FILENAME

    ctx = AbpContext()
    if config_path.is_file():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            ctx = AbpContext(**{k: data.get(k, "") for k in AbpContext().__dict__})
        except (OSError, json.JSONDecodeError, TypeError):
            ctx = AbpContext()

    # Fill from detection where config is empty
    for field_name in ctx.__dict__:
        if not getattr(ctx, field_name):
            setattr(ctx, field_name, getattr(detected, field_name, "") or "")

    # Prompt for anything still missing
    needs_save = False
    if not ctx.project_name:
        ctx.project_name = _prompt("Project name (e.g. MyProject)")
        needs_save = True
    if not ctx.root_namespace:
        ctx.root_namespace = _prompt("Root namespace", ctx.project_name)
        needs_save = True
    if not ctx.template_type:
        ctx.template_type = _prompt(
            "Template type (nolayers/layered/microservice)", "nolayers"
        )
        needs_save = True
    if not ctx.data_provider:
        ctx.data_provider = _prompt("Data provider (mongodb/efcore)", "mongodb")
        needs_save = True
    if not ctx.solution_root:
        ctx.solution_root = str(sln_root)
    if not ctx.project_root:
        ctx.project_root = _prompt(
            "Main project path (relative to solution root)",
            f"src/{ctx.project_name}",
        )
        needs_save = True

    if needs_save:
        try:
            config_path.write_text(
                json.dumps(ctx.as_dict(), indent=2), encoding="utf-8"
            )
            print(f"Saved config to {config_path}", file=sys.stderr)
        except OSError as e:
            print(f"Warning: could not save config: {e}", file=sys.stderr)

    return ctx


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")


def resolve_placeholders(text: str, ctx: AbpContext) -> str:
    """
    Replace placeholders of the form {{NAME}} with values from ctx.

    Supported keys:
      PROJECT_NAME, ROOT_NAMESPACE, TEMPLATE_TYPE, DATA_PROVIDER,
      PROJECT_ROOT, SOLUTION_ROOT
    """
    mapping = {
        "PROJECT_NAME": ctx.project_name,
        "ROOT_NAMESPACE": ctx.root_namespace,
        "TEMPLATE_TYPE": ctx.template_type,
        "DATA_PROVIDER": ctx.data_provider,
        "PROJECT_ROOT": ctx.project_root,
        "SOLUTION_ROOT": ctx.solution_root,
    }

    def _sub(m: re.Match) -> str:
        key = m.group(1)
        return mapping.get(key, m.group(0))

    return _PLACEHOLDER_RE.sub(_sub, text)


if __name__ == "__main__":
    # CLI: print detected/loaded context as JSON
    import argparse

    parser = argparse.ArgumentParser(description="ABP project context detector")
    parser.add_argument("--cwd", default=None, help="Override working directory")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Auto-detect only; do not prompt for missing fields",
    )
    args = parser.parse_args()

    if args.no_prompt:
        ctx = detect_abp_project(args.cwd)
    else:
        ctx = load_or_prompt_config(args.cwd)

    print(json.dumps(ctx.as_dict(), indent=2))
