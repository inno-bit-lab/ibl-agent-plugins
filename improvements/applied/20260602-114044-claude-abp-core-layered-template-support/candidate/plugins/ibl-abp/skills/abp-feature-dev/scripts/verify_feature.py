"""
verify_feature.py — Final validation of a scaffolded ABP feature.

After running scaffold_entity.py and completing the manual merge steps
(permissions, mapper, localization, DbContext registration), this script
verifies that the feature is wired correctly end-to-end.

It does NOT modify anything. All findings are printed as `[OK]`, `[WARN]`,
or `[FAIL]` markers. Exit code is non-zero if any `FAIL` finding occurs.

Usage:
    python verify_feature.py --entity Customer
    python verify_feature.py --entity Customer --no-build
    python verify_feature.py --entity Customer --strict   # warnings → failures

Checks performed:
    1. Entity file exists with the expected namespace
    2. DTOs exist (Dto, CreateUpdateDto, GetInput, optionally Lookup/Excel)
    3. AppService + interface exist
    4. DbContext has an IMongoCollection<Entity> and modelBuilder.Entity<Entity>
       registration (for MongoDB)
    5. Permissions class has the {Plural} nested class
    6. PermissionDefinitionProvider mentions {Plural}.Default
    7. Central mapper file contains an Entity→EntityDto mapper
    8. At least one language file has the Permission:{Plural} key
    9. If --lifecycle was used: DomainErrorCodes has the {Plural} block
    10. Tenant data seed contributor (if one exists) grants the new
        {Plural}.* permissions to its admin role. WARN-level: skipping
        this leaves the new sidebar entry hidden behind the permission
        guard until a manual grant via Admin Console.
    11. (Optional) `dotnet build` succeeds (skipped with --no-build)
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Windows default console is cp1252 — arrows (→) and other Unicode in findings
# crash the print() call. Force stdout/stderr to utf-8 with a fallback so the
# script never dies on a cosmetic character.
for _stream_attr in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_attr, None)
    if _stream is not None and getattr(_stream, "encoding", "").lower() != "utf-8":
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # py3.7+
        except (AttributeError, io.UnsupportedOperation):
            pass

_ABP_CORE_SCRIPTS = str(Path(__file__).resolve().parents[2] / "abp-core" / "scripts")
if _ABP_CORE_SCRIPTS not in sys.path:
    sys.path.insert(0, _ABP_CORE_SCRIPTS)

from abp_context import load_or_prompt_config, resolve_artifact  # noqa: E402


@dataclass
class Finding:
    level: str  # OK | WARN | FAIL
    message: str


def _feature_artifacts(ctx, base: Path, entity: str, plural: str):
    """Resolve the per-template (filename, absolute path, expected namespace) of
    every file scaffold_entity.py produces. The same call works for nolayers
    (one project) and layered (files fan out across projects) because the
    locations come from abp_context.resolve_artifact()."""
    def _loc(kind: str):
        return resolve_artifact(ctx, kind, plural)

    spec = [
        ("entity",               f"{entity}.cs",                _loc("entity")),
        ("dto",                  f"{entity}Dto.cs",             _loc("dto")),
        ("create_update_dto",    f"CreateUpdate{entity}Dto.cs", _loc("dto")),
        ("get_input",            f"Get{plural}Input.cs",        _loc("dto")),
        ("appservice_interface", f"I{entity}AppService.cs",     _loc("appservice_interface")),
        ("appservice_impl",      f"{entity}AppService.cs",      _loc("appservice_impl")),
    ]
    return [
        (kind, filename, base / loc.dir / filename, loc.namespace)
        for kind, filename, loc in spec
    ]


def _check_files_exist(ctx, base: Path, entity: str, plural: str) -> list[Finding]:
    findings: list[Finding] = []
    for _kind, _fn, path, _ns in _feature_artifacts(ctx, base, entity, plural):
        rel = path.relative_to(base) if base in path.parents else path
        if path.is_file():
            findings.append(Finding("OK", f"exists: {rel}"))
        else:
            findings.append(Finding("FAIL", f"missing: {rel}"))
    return findings


def _check_namespaces(ctx, base: Path, entity: str, plural: str) -> list[Finding]:
    findings: list[Finding] = []
    # Verify the namespace of the three load-bearing files (entity, output DTO,
    # AppService impl). The resolver supplies the expected value per template.
    interesting = {"entity", "dto", "appservice_impl"}
    for kind, _fn, path, ns in _feature_artifacts(ctx, base, entity, plural):
        if kind not in interesting or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"namespace\s+{re.escape(ns)}\s*;", text):
            findings.append(Finding("OK", f"namespace {ns} in {path.name}"))
        else:
            findings.append(Finding("FAIL", f"namespace mismatch in {path.name}: expected {ns}"))
    return findings


def _check_dbcontext(sln_root: Path, entity: str, plural: str) -> list[Finding]:
    candidates = [
        p for p in sln_root.rglob("*MongoDbContext.cs")
        if "Migration" not in p.as_posix() and "obj" not in p.as_posix()
    ]
    if not candidates:
        return [Finding("WARN", "no *MongoDbContext.cs found — skip DbContext check")]
    findings: list[Finding] = []
    for ctx in candidates:
        text = ctx.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"IMongoCollection<\s*{re.escape(entity)}\s*>", text):
            findings.append(Finding("OK", f"IMongoCollection<{entity}> in {ctx.name}"))
        else:
            findings.append(Finding("FAIL",
                f"DbContext {ctx.name} missing IMongoCollection<{entity}>. "
                f"Run abp-mongodb register_entity_in_context.py."))
        if re.search(rf"modelBuilder\.Entity<\s*{re.escape(entity)}\s*>", text):
            findings.append(Finding("OK", f"modelBuilder.Entity<{entity}> in {ctx.name}"))
        else:
            findings.append(Finding("WARN",
                f"DbContext {ctx.name} missing modelBuilder.Entity<{entity}> "
                "(collection name will default to class name)."))
    return findings


def _check_permissions(sln_root: Path, entity: str, plural: str,
                       root_ns: str) -> list[Finding]:
    findings: list[Finding] = []
    perms_files = list(sln_root.rglob(f"{root_ns}Permissions.cs"))
    if not perms_files:
        return [Finding("WARN", f"no {root_ns}Permissions.cs found")]
    for p in perms_files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"static\s+class\s+{re.escape(plural)}\b", text):
            findings.append(Finding("OK", f"Permissions.{plural} block in {p.name}"))
        else:
            findings.append(Finding("FAIL",
                f"{p.name} is missing the `public static class {plural}` block. "
                f"Merge from _permissions_snippet.txt."))

    provider_files = list(sln_root.rglob(f"{root_ns}PermissionDefinitionProvider.cs"))
    for p in provider_files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"{re.escape(root_ns)}Permissions\.{re.escape(plural)}\.Default", text):
            findings.append(Finding("OK", f"{plural}.Default registered in {p.name}"))
        else:
            findings.append(Finding("FAIL",
                f"{p.name} doesn't register {plural} permissions. "
                f"Merge from _permissions_snippet.txt."))
    return findings


def _check_mapper(sln_root: Path, entity: str) -> list[Finding]:
    findings: list[Finding] = []
    mapper_files = list(sln_root.rglob("*Mappers.cs"))
    if not mapper_files:
        return [Finding("WARN", "no central *Mappers.cs found (project may use AutoMapper)")]
    for p in mapper_files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"MapperBase<\s*{re.escape(entity)}\s*,\s*{re.escape(entity)}Dto\s*>", text):
            findings.append(Finding("OK", f"{entity} → {entity}Dto mapper in {p.name}"))
            return findings
    return [Finding("FAIL",
        f"No {entity} → {entity}Dto Mapperly mapper found. "
        f"Merge from _mapper_snippet.txt.")]


def _check_localization(sln_root: Path, plural: str, root_ns: str) -> list[Finding]:
    findings: list[Finding] = []
    lang_files = [p for p in sln_root.rglob("Localization/**/*.json") if p.is_file()]
    if not lang_files:
        return [Finding("WARN", "no localization files found")]
    required_key = f"Permission:{plural}"
    for p in lang_files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if required_key in text:
            findings.append(Finding("OK", f"`{required_key}` present in {p.name}"))
        else:
            findings.append(Finding("WARN",
                f"{p.name} missing `{required_key}` "
                "(merge _localization_snippet.json)."))
    return findings


def _entity_has_enum(ctx, base: Path, entity: str, plural: str) -> bool:
    """Returns True if the entity references at least one of its declared enums.

    The enum files live next to the entity in nolayers but in Domain.Shared in
    layered, so we resolve both locations rather than assuming siblings.
    """
    entity_file = base / resolve_artifact(ctx, "entity", plural).dir / f"{entity}.cs"
    if not entity_file.is_file():
        return False
    enum_dir = base / resolve_artifact(ctx, "enum", plural).dir
    sibling_enums: set[str] = set()
    if enum_dir.is_dir():
        for cs in enum_dir.glob("*.cs"):
            text = cs.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"^\s*public\s+enum\s+(\w+)", text, re.MULTILINE):
                sibling_enums.add(m.group(1))
    if not sibling_enums:
        return False
    text = entity_file.read_text(encoding="utf-8", errors="ignore")
    return any(re.search(rf"\b{re.escape(name)}\b", text) for name in sibling_enums)


def _check_enum_string_setup(sln_root: Path) -> list[Finding]:
    """Delegate to abp-mongodb/scripts/verify_enum_string_setup.py.

    Only invoked when the scaffolded entity actually has enums; otherwise
    we'd report findings on a project where no one cares about enum
    representation yet.
    """
    script = Path(__file__).resolve().parents[2] / "abp-mongodb" / "scripts" / "verify_enum_string_setup.py"
    if not script.is_file():
        return [Finding("WARN",
            f"abp-mongodb verify_enum_string_setup.py not found at {script}; "
            "skipping enum-string consistency check.")]
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--cwd", str(sln_root)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return [Finding("WARN", f"could not run enum-string check: {e}")]
    findings: list[Finding] = []
    out = (result.stdout or "") + (result.stderr or "")
    # Surface the sub-script's individual lines verbatim — the user gets the
    # same actionable detail they'd see running it directly.
    has_fail = False
    for line in out.splitlines():
        if line.startswith("[FAIL]"):
            findings.append(Finding("FAIL", "enum-string: " + line[len("[FAIL]"):].strip()))
            has_fail = True
        elif line.startswith("[WARN]"):
            findings.append(Finding("WARN", "enum-string: " + line[len("[WARN]"):].strip()))
        elif line.startswith("[OK]"):
            findings.append(Finding("OK", "enum-string: " + line[len("[OK]"):].strip()))
    if has_fail:
        findings.append(Finding("FAIL",
            "Run `python <skills-root>/abp-mongodb/scripts/verify_enum_string_setup.py --fix` "
            "then re-run `migrate-database`."))
    elif not findings:
        findings.append(Finding("WARN", "enum-string check produced no output (likely a script bug)"))
    return findings


def _check_domain_errors(ctx, base: Path, plural: str, root_ns: str) -> list[Finding]:
    code_file = (base / resolve_artifact(ctx, "error_codes", plural).dir
                 / f"{root_ns}DomainErrorCodes.cs")
    if not code_file.is_file():
        return [Finding("WARN", f"{root_ns}DomainErrorCodes.cs not found (lifecycle: no)")]
    text = code_file.read_text(encoding="utf-8", errors="ignore")
    if re.search(rf"static\s+class\s+{re.escape(plural)}\b", text):
        return [Finding("OK", f"DomainErrorCodes.{plural} present")]
    return [Finding("WARN", f"DomainErrorCodes.{plural} missing — only relevant if entity has a lifecycle")]


def _check_seed_contributor_grants(sln_root: Path, plural: str,
                                   root_ns: str) -> list[Finding]:
    """Warn if a tenant data seed contributor exists but doesn't grant the
    new {Plural}.* permissions to its admin role.

    The contributor pattern: any *.cs under the project that implements
    IDataSeedContributor AND calls IPermissionManager.SetForRoleAsync (or a
    GrantIfMissingAsync helper) is considered a candidate. If at least one
    such file is found but none mention `{root_ns}Permissions.{plural}`,
    emit a WARN — the developer probably forgot to grant.

    Missing entirely (no contributor at all) is FINE — the project may rely
    on the Admin Console UI. We only nag when the pattern is clearly there.
    """
    # Find candidates: IDataSeedContributor + a SetForRoleAsync/GrantIfMissingAsync call.
    candidates: list[Path] = []
    for cs in sln_root.rglob("*.cs"):
        # Skip bin/obj and node_modules-style directories.
        parts = {p.lower() for p in cs.parts}
        if parts & {"bin", "obj", "node_modules", ".git"}:
            continue
        try:
            text = cs.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if ("IDataSeedContributor" in text and
            ("SetForRoleAsync" in text or "GrantIfMissingAsync" in text)):
            candidates.append(cs)

    if not candidates:
        return [Finding(
            "WARN",
            f"no tenant data seed contributor found that grants permissions to roles. "
            f"If the project relies on Admin Console for permission grants, this is fine; "
            f"otherwise the user won't see the new sidebar entry until you grant "
            f"{root_ns}Permissions.{plural}.* manually."
        )]

    findings: list[Finding] = []
    for cs in candidates:
        text = cs.read_text(encoding="utf-8", errors="ignore")
        # Look for any mention of {root_ns}Permissions.{plural} (e.g.
        # Ibl360Permissions.Accounts.Default).
        pat = rf"{re.escape(root_ns)}Permissions\.{re.escape(plural)}\b"
        if re.search(pat, text):
            findings.append(Finding(
                "OK",
                f"{cs.name} grants {root_ns}Permissions.{plural}.* to a role"
            ))
        else:
            findings.append(Finding(
                "WARN",
                f"{cs.name} grants permissions to roles but does NOT mention "
                f"{root_ns}Permissions.{plural}.*. The default admin won't see "
                f"the new sidebar entry until you add the 4 grants and re-run "
                f"`migrate-database.ps1`. See "
                f"references/data-seeding.md in abp-feature-dev."
            ))
    return findings


def _run_build(ctx, sln_root: Path, base: Path) -> list[Finding]:
    """Run dotnet build with apphost copy disabled (avoids Windows file lock).

    Layered solutions span several projects, so building one project compiles
    too little. We build the whole solution when a solution file is present
    (covering Domain, Application, MongoDB, ...) and otherwise fall back to the
    AppService's project (which in nolayers is the single project)."""
    sln = next(
        (p for ext in ("*.slnx", "*.sln", "*.abpsln") for p in sln_root.glob(ext)),
        None,
    )
    if sln is not None:
        build_target = [str(sln)]
        cwd = sln_root
    else:
        proj = base / resolve_artifact(ctx, "appservice_impl", "X").project_dir
        if not next(proj.glob("*.csproj"), None):
            return [Finding("WARN", "no solution or *.csproj found — skipping build check")]
        build_target = []
        cwd = proj
    try:
        result = subprocess.run(
            ["dotnet", "build", *build_target, "--nologo", "-clp:NoSummary",
             "-p:UseAppHost=false"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return [Finding("WARN", f"could not run dotnet build: {e}")]
    if result.returncode == 0:
        return [Finding("OK", "dotnet build succeeded")]
    err = (result.stdout or "") + (result.stderr or "")
    # Trim to first 20 lines of error
    short = "\n".join(line for line in err.splitlines() if "error" in line.lower())[:1200]
    return [Finding("FAIL", f"dotnet build failed:\n{short}")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an ABP scaffolded feature is wired correctly")
    parser.add_argument("--entity", required=False, help="Entity name")
    parser.add_argument("--plural", help="Plural / folder name (default: entity + 's')")
    parser.add_argument("--no-build", action="store_true", help="Skip dotnet build")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--cwd", help="Override working directory")
    args = parser.parse_args()

    ctx = load_or_prompt_config(args.cwd)
    entity = args.entity
    if not entity:
        try:
            entity = input("Entity name: ").strip()
        except EOFError:
            entity = ""
    if not entity:
        print("Entity name required", file=sys.stderr)
        return 2
    plural = args.plural or (entity + "s")

    sln_root = Path(ctx.solution_root or os.getcwd())
    # Files are resolved relative to the solution root for both templates.
    base = sln_root

    all_findings: list[Finding] = []
    all_findings += _check_files_exist(ctx, base, entity, plural)
    all_findings += _check_namespaces(ctx, base, entity, plural)
    all_findings += _check_dbcontext(sln_root, entity, plural)
    all_findings += _check_permissions(sln_root, entity, plural, ctx.root_namespace)
    all_findings += _check_mapper(sln_root, entity)
    all_findings += _check_localization(sln_root, plural, ctx.root_namespace)
    all_findings += _check_domain_errors(ctx, base, plural, ctx.root_namespace)
    all_findings += _check_seed_contributor_grants(sln_root, plural, ctx.root_namespace)

    if _entity_has_enum(ctx, base, entity, plural):
        all_findings += _check_enum_string_setup(sln_root)

    if not args.no_build:
        all_findings += _run_build(ctx, sln_root, base)

    icons = {"OK": "[OK]  ", "WARN": "[WARN]", "FAIL": "[FAIL]"}
    counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    for f in all_findings:
        print(f"{icons.get(f.level, '?')} {f.message}")
        counts[f.level] = counts.get(f.level, 0) + 1

    print()
    print(f"Summary: {counts['OK']} OK, {counts['WARN']} warnings, {counts['FAIL']} failures")

    if counts["FAIL"] > 0:
        return 1
    if args.strict and counts["WARN"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
