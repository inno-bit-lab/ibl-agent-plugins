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


# =============================================================================
#  Layer / artifact resolution — the heart of dual-template support
# =============================================================================
#
# ABP ships several solution templates that lay the same code out differently:
#
#   * nolayers (a.k.a. "single-layer" / Simple Monolith / the IBL360 template):
#       ONE project. The layer a class belongs to is expressed by a *folder*
#       and baked into the *namespace* — e.g. an entity lives in
#       `Entities/Books/Book.cs` with namespace `Root.Entities.Books`, a DTO in
#       `Services/Dtos/Books/` with namespace `Root.Services.Dtos.Books`.
#
#   * layered (the DDD template — what IBLTermocasa uses):
#       SEPARATE projects (`*.Domain`, `*.Domain.Shared`, `*.Application`,
#       `*.Application.Contracts`, `*.MongoDB`/`*.EntityFrameworkCore`, ...).
#       The layer is expressed by the *physical project*, while the namespace is
#       FLAT — entity, DTO and AppService for the `Books` aggregate ALL share
#       namespace `Root.Books`, just living in different projects. Two namespaces
#       are special-cased because the real templates do so: persistence code is
#       `Root.MongoDB` / `Root.EntityFrameworkCore` and authorization code is
#       `Root.Permissions`.
#
# Rather than scatter `if template_type == ...` across seven skills, every skill
# asks THIS module "where does artifact X for aggregate Y go?" and gets back a
# directory (relative to the solution root) plus a namespace. Get this table
# right once and the whole toolkit follows.
#
# A correctness note that drives the layered table: `Application.Contracts`
# references `Domain.Shared` but NOT `Domain`. So any enum/constant a DTO needs
# must live in `Domain.Shared`, never in `Domain` — otherwise the contracts
# project won't compile. That is why `enum`/`consts` resolve to `domain_shared`
# in the layered map even though the entity that also uses them lives in
# `Domain`. (In nolayers everything is one project, so the point is moot and
# enums sit next to the entity, matching the historical scaffolder output.)

# data_provider -> the persistence project's suffix and inner folder
_DATA_LAYER = {
    "mongodb": ("MongoDB", "MongoDb"),          # project suffix, inner folder
    "efcore": ("EntityFrameworkCore", "EntityFrameworkCore"),
}

# logical layer -> project-name suffix for the LAYERED/microservice templates.
# `None` means "resolved dynamically" (data layer) or "the single project" (main).
_LAYER_SUFFIX = {
    "domain": "Domain",
    "domain_shared": "Domain.Shared",
    "application": "Application",
    "contracts": "Application.Contracts",
    "data": None,        # -> _DATA_LAYER[data_provider]
    "httpapi": "HttpApi",
    "host": "HttpApi.Host",
    "main": None,        # -> the single nolayers project (ctx.project_root)
}

# artifact kind -> (logical layer, subfolder template, namespace template)
# Templates accept {plural}, {root}, {datadir}, {datans}.
_ARTIFACT_LAYERED = {
    "entity":               ("domain",        "{plural}",            "{root}.{plural}"),
    "enum":                 ("domain_shared", "{plural}",            "{root}.{plural}"),
    "consts":               ("domain_shared", "{plural}",            "{root}.{plural}"),
    "error_codes":          ("domain_shared", "",                    "{root}"),
    "eto":                  ("domain_shared", "{plural}",            "{root}.{plural}"),
    "repo_interface":       ("domain",        "{plural}",            "{root}.{plural}"),
    "domain_service":       ("domain",        "{plural}",            "{root}.{plural}"),
    "data_seed":            ("domain",        "{plural}",            "{root}.{plural}"),
    "dto":                  ("contracts",     "{plural}",            "{root}.{plural}"),
    "appservice_interface": ("contracts",     "{plural}",            "{root}.{plural}"),
    "permissions":          ("contracts",     "Permissions",         "{root}.Permissions"),
    "appservice_impl":      ("application",   "{plural}",            "{root}.{plural}"),
    "mapper":               ("application",   "",                    "{root}"),
    "repo_impl":            ("data",          "{datadir}/{plural}",  "{root}.{datans}"),
    "data_context":         ("data",          "{datadir}",           "{root}.{datans}"),
    "localization":         ("domain_shared", "Localization/{root}", ""),
}

# Historical single-project layout (IBL360). Kept byte-compatible with the
# pre-existing scaffolder so nolayers output does not regress.
_ARTIFACT_NOLAYERS = {
    "entity":               ("main", "Entities/{plural}",      "{root}.Entities.{plural}"),
    "enum":                 ("main", "Entities/{plural}",      "{root}.Entities.{plural}"),
    "consts":               ("main", "Entities/{plural}",      "{root}.Entities.{plural}"),
    "error_codes":          ("main", "",                       "{root}"),
    "eto":                  ("main", "Entities/{plural}",      "{root}.Entities.{plural}"),
    "repo_interface":       ("main", "Data/{plural}",          "{root}.Data.{plural}"),
    "domain_service":       ("main", "Entities/{plural}",      "{root}.Entities.{plural}"),
    "data_seed":            ("main", "Data",                   "{root}"),
    "dto":                  ("main", "Services/Dtos/{plural}", "{root}.Services.Dtos.{plural}"),
    "appservice_interface": ("main", "Services/{plural}",      "{root}.Services.{plural}"),
    "permissions":          ("main", "Permissions",            "{root}.Permissions"),
    "appservice_impl":      ("main", "Services/{plural}",      "{root}.Services.{plural}"),
    "mapper":               ("main", "ObjectMapping",          "{root}"),
    "repo_impl":            ("main", "Data/{plural}",          "{root}.Data.{plural}"),
    "data_context":         ("main", "Data",                   "{root}.Data"),
    "localization":         ("main", "Localization/{root}",    ""),
}


@dataclass
class ArtifactLocation:
    """Where one generated artifact belongs, relative to the solution root."""
    kind: str
    project_dir: str   # the layer project, e.g. "src/Foo.Domain" (nolayers: the single project)
    dir: str           # project_dir + subfolder, e.g. "src/Foo.Domain/Books"
    namespace: str     # the C# namespace, e.g. "Foo.Books"


def _src_root(ctx: AbpContext) -> str:
    """The directory that contains the project folders ("src", or "" for a
    flat layout). Derived from project_root's parent so it works regardless of
    whether the solution uses a src/ folder."""
    pr = (ctx.project_root or "").replace("\\", "/").strip("/")
    return pr.rsplit("/", 1)[0] if "/" in pr else ""


def _is_layered(ctx: AbpContext) -> bool:
    return (ctx.template_type or "nolayers") in ("layered", "microservice")


def data_layer(ctx: AbpContext) -> tuple[str, str]:
    """(project suffix, inner folder) for the active persistence provider."""
    return _DATA_LAYER.get(ctx.data_provider or "mongodb", _DATA_LAYER["mongodb"])


def layer_project_dir(ctx: AbpContext, layer: str) -> str:
    """Relative path (from solution root) of the project for a logical layer.

    In nolayers every layer collapses onto the single main project, so callers
    that use {{DOMAIN_PROJECT}} etc. transparently get the right thing on both
    templates."""
    if not _is_layered(ctx) or layer == "main":
        return (ctx.project_root or ctx.project_name).replace("\\", "/")
    suffix = data_layer(ctx)[0] if layer == "data" else _LAYER_SUFFIX.get(layer)
    folder = f"{ctx.project_name}.{suffix}" if suffix else ctx.project_name
    src = _src_root(ctx)
    return f"{src}/{folder}" if src else folder


def test_project_dir(ctx: AbpContext, layer: str = "application") -> str:
    """Relative path of a test project. Layered solutions split tests by layer
    (`*.Application.Tests`, `*.Domain.Tests`, `*.MongoDB.Tests`); nolayers has a
    single `*.Tests` project. `test_root` is taken as the sibling of src_root."""
    src = _src_root(ctx)
    test_root = (src.rsplit("/", 1)[0] + "/test") if "/" in src else "test" if src else ""
    if not _is_layered(ctx):
        folder = f"{ctx.project_name}.Tests"
    elif layer == "data":
        folder = f"{ctx.project_name}.{data_layer(ctx)[0]}.Tests"
    else:
        suffix = _LAYER_SUFFIX.get(layer, "Application")
        folder = f"{ctx.project_name}.{suffix}.Tests"
    return f"{test_root}/{folder}" if test_root else folder


def resolve_artifact(ctx: AbpContext, kind: str, plural: str = "") -> ArtifactLocation:
    """Resolve where an artifact of `kind` for the `plural` aggregate belongs.

    `kind` is one of the keys in _ARTIFACT_LAYERED / _ARTIFACT_NOLAYERS, e.g.
    "entity", "enum", "dto", "appservice_impl", "repo_impl", "permissions".
    Returns directories relative to the solution root plus the C# namespace.
    """
    table = _ARTIFACT_LAYERED if _is_layered(ctx) else _ARTIFACT_NOLAYERS
    if kind not in table:
        raise KeyError(
            f"Unknown artifact kind {kind!r}. "
            f"Known: {sorted(set(_ARTIFACT_LAYERED) | set(_ARTIFACT_NOLAYERS))}"
        )
    layer, sub_t, ns_t = table[kind]
    root = ctx.root_namespace or ctx.project_name
    proj_suffix, datadir = data_layer(ctx)
    fmt = {"plural": plural, "root": root, "datadir": datadir, "datans": proj_suffix}

    project_dir = layer_project_dir(ctx, layer)
    sub = sub_t.format(**fmt).strip("/")
    full_dir = f"{project_dir}/{sub}" if sub else project_dir
    namespace = ns_t.format(**fmt)
    return ArtifactLocation(
        kind=kind,
        project_dir=project_dir.replace("\\", "/"),
        dir=full_dir.replace("\\", "/"),
        namespace=namespace,
    )


def layout_summary(ctx: AbpContext, plural: str = "Books") -> dict:
    """Resolve every artifact kind for a sample aggregate — handy for tests and
    for showing the user what the active template implies."""
    kinds = sorted(set(_ARTIFACT_LAYERED) | set(_ARTIFACT_NOLAYERS))
    return {
        k: {"dir": loc.dir, "namespace": loc.namespace}
        for k in kinds
        for loc in [resolve_artifact(ctx, k, plural)]
    }


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")


def resolve_placeholders(text: str, ctx: AbpContext) -> str:
    """
    Replace placeholders of the form {{NAME}} with values from ctx.

    Project-wide keys:
      PROJECT_NAME, ROOT_NAMESPACE, TEMPLATE_TYPE, DATA_PROVIDER,
      PROJECT_ROOT, SOLUTION_ROOT

    Per-layer project keys (collapse onto PROJECT_ROOT in nolayers, so a single
    template string works on both templates):
      DOMAIN_PROJECT, DOMAIN_SHARED_PROJECT, APPLICATION_PROJECT,
      CONTRACTS_PROJECT, DATA_PROJECT, HTTPAPI_PROJECT, HOST_PROJECT
    """
    mapping = {
        "PROJECT_NAME": ctx.project_name,
        "ROOT_NAMESPACE": ctx.root_namespace,
        "TEMPLATE_TYPE": ctx.template_type,
        "DATA_PROVIDER": ctx.data_provider,
        "PROJECT_ROOT": ctx.project_root,
        "SOLUTION_ROOT": ctx.solution_root,
        "DOMAIN_PROJECT": layer_project_dir(ctx, "domain"),
        "DOMAIN_SHARED_PROJECT": layer_project_dir(ctx, "domain_shared"),
        "APPLICATION_PROJECT": layer_project_dir(ctx, "application"),
        "CONTRACTS_PROJECT": layer_project_dir(ctx, "contracts"),
        "DATA_PROJECT": layer_project_dir(ctx, "data"),
        "HTTPAPI_PROJECT": layer_project_dir(ctx, "httpapi"),
        "HOST_PROJECT": layer_project_dir(ctx, "host"),
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
    parser.add_argument(
        "--show-layout",
        nargs="?",
        const="Books",
        default=None,
        metavar="PLURAL",
        help="Also print the resolved directory + namespace for every artifact "
        "kind, using PLURAL as a sample aggregate (default: Books).",
    )
    args = parser.parse_args()

    if args.no_prompt or args.show_layout is not None:
        ctx = detect_abp_project(args.cwd)
    else:
        ctx = load_or_prompt_config(args.cwd)

    out = ctx.as_dict()
    if args.show_layout is not None:
        out["layout"] = layout_summary(ctx, args.show_layout)
    print(json.dumps(out, indent=2))
