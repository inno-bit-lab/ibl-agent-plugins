"""
verify_enum_string_setup.py — Check that an ABP+MongoDB project consistently
stores AND serializes enums as strings, end-to-end.

Three layers must agree, otherwise you get silent mismatches (e.g. MongoDB
stores "Active" but the REST API returns 1, or Swagger says `type: integer`):

    1. MongoDB storage      → ConventionRegistry + EnumRepresentationConvention
    2. REST API serializer  → JsonStringEnumConverter on
                              Microsoft.AspNetCore.Mvc.JsonOptions
    3. ABP-internal JSON    → JsonStringEnumConverter on
                              Volo.Abp.Json.SystemTextJson.AbpSystemTextJsonSerializerOptions
                              (used by ABP proxies, dynamic HTTP clients,
                              and outbound integration JSON)

Swashbuckle (Swagger / OpenAPI) reads from MVC's JsonOptions automatically —
if (2) is in place, the generated OpenAPI schema correctly emits
`type: string, enum: [...]` for every enum, no extra config needed.

The script inspects the project's `*Module.cs`, reports what's missing,
prints a ready-to-paste snippet, and reminds the user to re-seed
(`migrate-database.ps1`) so any seed-time data that embeds enum values
is rewritten with the new representation.

Usage:
    python verify_enum_string_setup.py
    python verify_enum_string_setup.py --cwd /path/to/solution
    python verify_enum_string_setup.py --fix       # patch *Module.cs in place
    python verify_enum_string_setup.py --strict    # warnings → failures

Exit code: 0 if everything is wired, 1 if any check fails (or warnings under
--strict). The --fix mode never deletes anything; it only inserts the missing
blocks and prints the diff.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_ABP_CORE_SCRIPTS = str(Path(__file__).resolve().parents[2] / "abp-core" / "scripts")
if _ABP_CORE_SCRIPTS not in sys.path:
    sys.path.insert(0, _ABP_CORE_SCRIPTS)

try:
    from abp_context import load_or_prompt_config  # type: ignore
    HAVE_CONTEXT = True
except Exception:
    HAVE_CONTEXT = False


@dataclass
class Finding:
    level: str  # OK | WARN | FAIL
    message: str
    fix_snippet: str | None = None


# ---------------------------------------------------------------------------
# Detection patterns. Loose enough to tolerate formatting variations, strict
# enough to avoid false positives (e.g. an unrelated comment that just
# mentions "EnumRepresentationConvention").
# ---------------------------------------------------------------------------

_CONVENTION_RE = re.compile(
    r"ConventionRegistry\.Register\s*\(.*?"
    r"EnumRepresentationConvention\s*\(\s*"
    r"(?:MongoDB\.Bson\.)?BsonType\.String",
    re.DOTALL,
)

_ASPNET_JSON_RE = re.compile(
    r"Configure\s*<\s*(?:Microsoft\.AspNetCore\.Mvc\.)?JsonOptions\s*>\s*\(.*?"
    r"JsonStringEnumConverter",
    re.DOTALL,
)

_ABP_JSON_RE = re.compile(
    r"Configure\s*<\s*(?:Volo\.Abp\.Json\.SystemTextJson\.)?AbpSystemTextJsonSerializerOptions\s*>"
    r"\s*\(.*?JsonStringEnumConverter",
    re.DOTALL,
)

_PRECONFIG_RE = re.compile(
    r"public\s+override\s+void\s+PreConfigureServices\s*\([^)]*\)\s*\{",
    re.DOTALL,
)
_CONFIG_RE = re.compile(
    r"public\s+override\s+void\s+ConfigureServices\s*\([^)]*\)\s*\{",
    re.DOTALL,
)


CONVENTION_SNIPPET = """\
// Store ALL enums as strings in MongoDB documents, automatically.
// Applies to every type registered after this point; must run in
// PreConfigureServices to be in place before the first BsonClassMap.
ConventionRegistry.Register(
    "{ROOT}EnumAsString",
    new MongoDB.Bson.Serialization.Conventions.ConventionPack
    {{
        new MongoDB.Bson.Serialization.Conventions.EnumRepresentationConvention(
            MongoDB.Bson.BsonType.String)
    }},
    _ => true);
"""

ASPNET_JSON_SNIPPET = """\
// REST API: surface enums as strings to match MongoDB storage.
// Swashbuckle reads from these JsonOptions, so the generated OpenAPI
// schema will also emit `type: string, enum: [...]` for free.
context.Services.Configure<Microsoft.AspNetCore.Mvc.JsonOptions>(o =>
    o.JsonSerializerOptions.Converters.Add(
        new System.Text.Json.Serialization.JsonStringEnumConverter()));
"""

ABP_JSON_SNIPPET = """\
// ABP-internal JSON (proxies, dynamic clients, integration events):
// keep the representation consistent with the REST surface above.
context.Services.Configure<Volo.Abp.Json.SystemTextJson.AbpSystemTextJsonSerializerOptions>(o =>
    o.JsonSerializerOptions.Converters.Add(
        new System.Text.Json.Serialization.JsonStringEnumConverter()));
"""


def _find_module_file(sln_root: Path, root_ns: str | None) -> Path | None:
    """Locate the project's main *Module.cs (skip migration/test variants)."""
    candidates: list[Path] = []
    pattern = f"{root_ns}Module.cs" if root_ns else "*Module.cs"
    for p in sln_root.rglob(pattern):
        s = p.as_posix()
        if any(part in s for part in ("/obj/", "/bin/", "Migration", ".Tests")):
            continue
        # Skip ABP framework module re-declarations
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "AbpModule" not in text:
            continue
        candidates.append(p)
    if not candidates:
        return None
    # Prefer the shortest path (top-level module file)
    return min(candidates, key=lambda p: len(p.as_posix()))


def _check_convention(module_text: str, root_ns: str) -> Finding:
    if _CONVENTION_RE.search(module_text):
        return Finding("OK", "EnumRepresentationConvention(BsonType.String) is registered")
    return Finding(
        "FAIL",
        "MongoDB will store enums as INTEGERS (driver default). "
        "Register a convention in PreConfigureServices.",
        fix_snippet=CONVENTION_SNIPPET.format(ROOT=root_ns),
    )


def _check_aspnet_json(module_text: str) -> Finding:
    if _ASPNET_JSON_RE.search(module_text):
        return Finding("OK", "JsonStringEnumConverter on MVC JsonOptions")
    return Finding(
        "FAIL",
        "REST API will return enums as INTEGERS — out of sync with MongoDB storage. "
        "Add JsonStringEnumConverter to MVC JsonOptions in ConfigureServices. "
        "This ALSO fixes Swagger/OpenAPI: Swashbuckle reads from these options.",
        fix_snippet=ASPNET_JSON_SNIPPET,
    )


def _check_abp_json(module_text: str) -> Finding:
    if _ABP_JSON_RE.search(module_text):
        return Finding("OK", "JsonStringEnumConverter on AbpSystemTextJsonSerializerOptions")
    return Finding(
        "WARN",
        "ABP-internal JSON serializer uses default enum representation. "
        "Outbound HTTP proxies and integration events may emit integers. "
        "Recommend adding JsonStringEnumConverter to AbpSystemTextJsonSerializerOptions.",
        fix_snippet=ABP_JSON_SNIPPET,
    )


def _apply_fixes(module_file: Path, missing: list[Finding]) -> bool:
    """Insert missing snippets idempotently. Returns True if file was modified."""
    text = module_file.read_text(encoding="utf-8")
    original = text
    changed = False

    convention_fix = next(
        (f for f in missing
         if f.fix_snippet and "EnumRepresentationConvention" in (f.fix_snippet or "")),
        None,
    )
    if convention_fix:
        m = _PRECONFIG_RE.search(text)
        if not m:
            print(f"[FAIL] Cannot --fix convention: no PreConfigureServices block in {module_file.name}.")
        else:
            indent = "        "
            snippet = "\n".join(indent + line for line in convention_fix.fix_snippet.splitlines())
            insert_at = m.end()
            text = text[:insert_at] + "\n" + snippet + "\n" + text[insert_at:]
            changed = True

    for f in missing:
        if not f.fix_snippet or "JsonStringEnumConverter" not in f.fix_snippet:
            continue
        m = _CONFIG_RE.search(text)
        if not m:
            print(f"[FAIL] Cannot --fix JSON converter: no ConfigureServices block in {module_file.name}.")
            continue
        indent = "        "
        snippet = "\n".join(indent + line for line in f.fix_snippet.splitlines())
        insert_at = m.end()
        text = text[:insert_at] + "\n" + snippet + "\n" + text[insert_at:]
        changed = True

    if changed and text != original:
        module_file.write_text(text, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cwd", help="Override the solution root")
    parser.add_argument("--module-file", help="Explicit path to *Module.cs (skip auto-detection)")
    parser.add_argument("--root-namespace", help="Root namespace (only needed when context cannot be resolved)")
    parser.add_argument("--fix", action="store_true",
                        help="Patch the *Module.cs in place to insert the missing blocks.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    sln_root: Path
    root_ns: str | None = args.root_namespace

    if HAVE_CONTEXT:
        try:
            ctx = load_or_prompt_config(args.cwd)
            sln_root = Path(ctx.solution_root or os.getcwd())
            root_ns = root_ns or ctx.root_namespace
        except Exception:
            sln_root = Path(args.cwd or os.getcwd())
    else:
        sln_root = Path(args.cwd or os.getcwd())

    if args.module_file:
        module_file = Path(args.module_file)
        if not module_file.is_file():
            print(f"[FAIL] --module-file does not exist: {module_file}", file=sys.stderr)
            return 2
    else:
        module_file = _find_module_file(sln_root, root_ns)
        if module_file is None:
            print("[FAIL] Could not locate a *Module.cs in the solution. "
                  "Pass --module-file explicitly.", file=sys.stderr)
            return 2

    print(f"Inspecting: {module_file}")

    if not root_ns:
        m = re.search(r"namespace\s+([\w.]+)\s*;", module_file.read_text(encoding="utf-8", errors="ignore"))
        root_ns = m.group(1).split(".")[-1] if m else "App"

    text = module_file.read_text(encoding="utf-8")
    findings = [
        _check_convention(text, root_ns),
        _check_aspnet_json(text),
        _check_abp_json(text),
    ]

    counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    icons = {"OK": "[OK]  ", "WARN": "[WARN]", "FAIL": "[FAIL]"}
    for f in findings:
        print(f"{icons[f.level]} {f.message}")
        counts[f.level] += 1

    missing = [f for f in findings if f.level in ("FAIL", "WARN") and f.fix_snippet]

    if args.fix and missing:
        print()
        print("--- Applying fixes ---")
        if _apply_fixes(module_file, missing):
            print(f"[OK]   Patched {module_file.name}. Re-run this script to confirm.")
            print()
            print(">> IMPORTANT: re-run migrate-database to rewrite any seed-time data")
            print("   that embedded enum values with the old representation:")
            print()
            print("       powershell -File migrate-database.ps1")
            print()
            print("   For pre-existing application data (Customer/Order/...), the")
            print("   driver still READS old-format documents; writes use the new")
            print("   representation. For a clean cutover, run a one-shot updateMany")
            print("   per collection that maps the integer values to their names.")
        else:
            print("[FAIL] Could not apply fixes. Insert the snippets manually.")
            return 1
    elif missing:
        print()
        print("--- Suggested fixes ---")
        if any("EnumRepresentationConvention" in (f.fix_snippet or "") for f in missing):
            print()
            print("In PreConfigureServices(), add:")
            print()
            for f in missing:
                if f.fix_snippet and "EnumRepresentationConvention" in f.fix_snippet:
                    print(f.fix_snippet)
        json_fixes = [f for f in missing if f.fix_snippet and "JsonStringEnumConverter" in f.fix_snippet]
        if json_fixes:
            print("In ConfigureServices(), add:")
            print()
            for f in json_fixes:
                print(f.fix_snippet)
        print(">> After applying, re-run `migrate-database` to refresh seed data,")
        print("   then re-run this script to confirm.")

    print()
    print(f"Summary: {counts['OK']} OK, {counts['WARN']} warnings, {counts['FAIL']} failures")

    if counts["FAIL"] > 0:
        return 1
    if args.strict and counts["WARN"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
