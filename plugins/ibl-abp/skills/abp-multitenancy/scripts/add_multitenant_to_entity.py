"""
add_multitenant_to_entity.py — Add IMultiTenant to an existing entity file.

Modifies an entity .cs file in-place to:
  1. Add `using Volo.Abp.MultiTenancy;` if missing.
  2. Append `, IMultiTenant` to the entity class declaration.
  3. Add a `public Guid? TenantId { get; set; }` property (public setter is
     intentional — IMultiTenant requires it settable).

Idempotent: if the entity already implements IMultiTenant, reports `[skip]`.

Usage:
  python add_multitenant_to_entity.py --entity-file path/to/Book.cs
  python add_multitenant_to_entity.py            # interactive

Notes:
- The script does NOT migrate existing data. Existing documents in MongoDB
  (or rows in SQL) will have NULL TenantId, which means "host-owned". If you
  intend them to belong to a specific tenant, run a one-off data update
  separately.
- Does NOT update the AbpMongoDbContext or DbContext — schema/collection
  registration is unaffected.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_ABP_CORE_SCRIPTS = str(Path(__file__).resolve().parents[2] / "abp-core" / "scripts")
if _ABP_CORE_SCRIPTS not in sys.path:
    sys.path.insert(0, _ABP_CORE_SCRIPTS)

from abp_context import load_or_prompt_config  # noqa: E402


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{label}{suffix}: ").strip() or default
    except EOFError:
        return default


def _ensure_using(text: str, ns: str) -> tuple[str, bool]:
    line = f"using {ns};"
    if line in text:
        return text, False
    lines = text.splitlines()
    last_using = -1
    for i, l in enumerate(lines):
        if l.strip().startswith("using "):
            last_using = i
    if last_using >= 0:
        lines.insert(last_using + 1, line)
    else:
        lines.insert(0, line)
    return "\n".join(lines), True


def _add_interface_to_class(text: str) -> tuple[str, bool, str | None]:
    """
    Find the entity class declaration and append `, IMultiTenant` to its base list.
    Returns (new_text, modified, entity_name).
    """
    # Match: `class Foo : Base<...>` or `class Foo : Base, ISomething`
    pattern = re.compile(
        r"(class\s+(\w+)\s*:\s*)(?P<bases>[^\{\r\n]+?)(\s*\{)",
        re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        # No base list — just `class Foo`. We need to add `: IMultiTenant`.
        pattern2 = re.compile(r"(class\s+(\w+))(\s*\{)", re.MULTILINE)
        m2 = pattern2.search(text)
        if not m2:
            return text, False, None
        if "IMultiTenant" in text:
            return text, False, m2.group(2)
        replacement = f"{m2.group(1)} : IMultiTenant{m2.group(3)}"
        return text[:m2.start()] + replacement + text[m2.end():], True, m2.group(2)

    bases = m.group("bases").strip().rstrip(",").strip()
    entity_name = m.group(2)

    if re.search(r"\bIMultiTenant\b", bases):
        return text, False, entity_name

    new_bases = bases + ", IMultiTenant"
    new_decl = m.group(1) + new_bases + m.group(4)
    return text[:m.start()] + new_decl + text[m.end():], True, entity_name


def _add_tenant_id_property(text: str, entity_name: str) -> tuple[str, bool]:
    """Insert `public Guid? TenantId { get; set; }` near the top of the class body."""
    if re.search(r"public\s+Guid\?\s+TenantId\s*\{\s*get\s*;\s*set\s*;\s*\}", text):
        return text, False

    # Locate class opening brace
    m = re.search(rf"class\s+{re.escape(entity_name)}\b[^{{]*\{{", text)
    if not m:
        return text, False
    insert_at = m.end()
    snippet = "\n    public Guid? TenantId { get; set; }\n"
    return text[:insert_at] + snippet + text[insert_at:], True


def main() -> int:
    parser = argparse.ArgumentParser(description="Make an entity multi-tenant (IMultiTenant)")
    parser.add_argument("--entity-file", help="Path to the entity .cs file")
    parser.add_argument("--cwd", help="Override working directory")
    args = parser.parse_args()

    load_or_prompt_config(args.cwd)   # ensures .abp-skills.json exists; ctx itself not needed here

    path_str = args.entity_file or _prompt("Path to entity .cs file")
    if not path_str:
        print("Entity file is required.", file=sys.stderr)
        return 2
    path = Path(path_str)
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    original = text

    text, added_using = _ensure_using(text, "Volo.Abp.MultiTenancy")
    text, added_interface, entity_name = _add_interface_to_class(text)
    if not entity_name:
        print("Could not locate the entity class declaration.", file=sys.stderr)
        return 2
    text, added_prop = _add_tenant_id_property(text, entity_name)

    if text == original:
        print(f"[skip] {entity_name} already implements IMultiTenant")
        return 0

    path.write_text(text, encoding="utf-8")
    print(f"[OK] {entity_name} is now IMultiTenant")
    if added_using:
        print("  + using Volo.Abp.MultiTenancy;")
    if added_interface:
        print("  + : IMultiTenant on class declaration")
    if added_prop:
        print("  + public Guid? TenantId { get; set; }")
    print(
        "\nNote: existing data will have NULL TenantId (= host-owned). "
        "Run a data migration if you need to assign existing records to a tenant."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
