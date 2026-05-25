"""
register_entity_in_context.py — Add an entity to an existing AbpMongoDbContext,
and optionally register a custom MongoDbRepository in the module.

Modifies an existing *MongoDbContext.cs in place:
  1. Adds `using <entity-namespace>;` if missing.
  2. Adds `IMongoCollection<TEntity> {Plural} => Collection<TEntity>();`
  3. Adds `modelBuilder.Entity<TEntity>(b => { b.CollectionName = "..."; });`
     inside CreateModel (creates the override if it doesn't exist).

If --register-repository is also passed, modifies the *Module.cs:
  4. Adds `using <repository-namespace>;` if missing.
  5. Adds `options.AddRepository<TEntity, TRepositoryImpl>();` inside the
     `AddMongoDbContext<>(options => {...})` call.

All steps are idempotent — re-running reports `[skip]` for things already done.

Usage:
    python register_entity_in_context.py --entity Book --plural Books \\
        --entity-namespace MyProject.Entities.Books

    python register_entity_in_context.py --entity Customer --plural Customers \\
        --entity-namespace MyProject.Entities.Customers \\
        --register-repository \\
        --repository-namespace MyProject.Data.Customers \\
        --repository-name MongoCustomerRepository

    python register_entity_in_context.py        # interactive
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


def _find_context_file(ctx) -> Path | None:
    sln = Path(ctx.solution_root) if ctx.solution_root else Path.cwd()
    candidates = list(sln.rglob("*MongoDbContext.cs"))
    candidates = [c for c in candidates if "Migration" not in c.as_posix() and "obj" not in c.as_posix()]
    return candidates[0] if candidates else None


def _find_module_file(ctx) -> Path | None:
    sln = Path(ctx.solution_root) if ctx.solution_root else Path.cwd()
    # Look for a *Module.cs that calls AddMongoDbContext
    for p in sln.rglob("*Module.cs"):
        if "obj" in p.as_posix() or "Migration" in p.as_posix():
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
            if "AddMongoDbContext" in t:
                return p
        except OSError:
            continue
    return None


def _ensure_using(text: str, namespace: str) -> tuple[str, bool]:
    using_line = f"using {namespace};"
    if using_line in text:
        return text, False
    lines = text.splitlines()
    last_using = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("using "):
            last_using = i
    if last_using >= 0:
        lines.insert(last_using + 1, using_line)
    else:
        lines.insert(0, using_line)
    return "\n".join(lines), True


def _add_collection_property(text: str, entity: str, plural: str) -> tuple[str, bool]:
    prop_signature = f"IMongoCollection<{entity}>"
    if prop_signature in text:
        return text, False

    prop_line = (
        f"    public IMongoCollection<{entity}> {plural} => Collection<{entity}>();"
    )

    matches = list(re.finditer(
        r"^[ \t]*public IMongoCollection<\w+>\s+\w+\s*=>\s*Collection<\w+>\(\);",
        text, re.MULTILINE,
    ))
    if matches:
        last = matches[-1]
        return text[: last.end()] + "\n" + prop_line + text[last.end():], True

    m = re.search(r"class\s+\w+MongoDbContext\b[^{]*\{", text)
    if not m:
        raise RuntimeError("Could not locate class declaration in context file")
    insert_at = m.end()
    return text[:insert_at] + "\n" + prop_line + "\n" + text[insert_at:], True


def _add_model_builder_entry(text: str, entity: str, plural: str) -> tuple[str, bool]:
    entry = (
        f"        modelBuilder.Entity<{entity}>(b =>\n"
        f"        {{\n"
        f"            b.CollectionName = \"{plural}\";\n"
        f"        }});"
    )
    if re.search(rf"modelBuilder\.Entity<\s*{re.escape(entity)}\s*>", text):
        return text, False

    m = re.search(
        r"protected\s+override\s+void\s+CreateModel\s*\(\s*IMongoModelBuilder\s+modelBuilder\s*\)\s*\{",
        text,
    )
    if m:
        i = m.end()
        depth = 1
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        if depth == 0:
            close = i - 1
            insertion = "\n\n" + entry + "\n    "
            return text[:close] + insertion + text[close:], True

    class_match = re.search(r"class\s+\w+MongoDbContext\b", text)
    if not class_match:
        raise RuntimeError("Could not locate class declaration")
    brace_open = text.find("{", class_match.end())
    if brace_open < 0:
        raise RuntimeError("Malformed class")
    depth = 1
    i = brace_open + 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth != 0:
        raise RuntimeError("Unbalanced braces in context file")
    class_close = i - 1
    create_model = (
        "\n    protected override void CreateModel(IMongoModelBuilder modelBuilder)\n"
        "    {\n"
        "        base.CreateModel(modelBuilder);\n\n"
        + entry
        + "\n    }\n"
    )
    return text[:class_close] + create_model + text[class_close:], True


def _add_repository_registration(text: str, entity: str, repository: str) -> tuple[str, bool]:
    """
    Insert `options.AddRepository<Entity, Repository>();` inside the
    AddMongoDbContext<X>(options => {...}) lambda.
    """
    pattern = re.compile(
        rf"options\.AddRepository<\s*{re.escape(entity)}\s*,\s*{re.escape(repository)}\s*>",
    )
    if pattern.search(text):
        return text, False

    # Find the AddMongoDbContext call and its lambda body
    m = re.search(
        r"AddMongoDbContext<\w+>\s*\(\s*options\s*=>\s*\{",
        text,
    )
    if not m:
        return text, False
    # Walk past the matching closing brace of the lambda
    i = m.end()
    depth = 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth != 0:
        return text, False
    close = i - 1
    insertion = f"            options.AddRepository<{entity}, {repository}>();\n"
    # Insert with reasonable indent, on its own line just before the closing }
    return text[:close] + insertion + "        " + text[close:], True


def _update_context(ctx_file: Path, entity: str, plural: str, entity_ns: str) -> list[str]:
    text = ctx_file.read_text(encoding="utf-8")
    original = text
    changes: list[str] = []

    text, added_using = _ensure_using(text, entity_ns)
    if added_using:
        changes.append(f"using {entity_ns};")
    text, added_prop = _add_collection_property(text, entity, plural)
    if added_prop:
        changes.append(f"IMongoCollection<{entity}> {plural} property")
    text, added_model = _add_model_builder_entry(text, entity, plural)
    if added_model:
        changes.append(f"modelBuilder.Entity<{entity}> registration")

    if text != original:
        ctx_file.write_text(text, encoding="utf-8")
    return changes


def _update_module(module_file: Path, entity: str, repository: str,
                   repository_ns: str, entity_ns: str) -> list[str]:
    text = module_file.read_text(encoding="utf-8")
    original = text
    changes: list[str] = []

    text, added_using_repo = _ensure_using(text, repository_ns)
    if added_using_repo:
        changes.append(f"using {repository_ns};")
    text, added_using_entity = _ensure_using(text, entity_ns)
    if added_using_entity:
        changes.append(f"using {entity_ns};")
    text, added_reg = _add_repository_registration(text, entity, repository)
    if added_reg:
        changes.append(f"options.AddRepository<{entity}, {repository}>()")

    if text != original:
        module_file.write_text(text, encoding="utf-8")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Register an entity in an AbpMongoDbContext")
    parser.add_argument("--entity", help="Entity class name (e.g. Customer)")
    parser.add_argument("--plural", help="Collection / property name (e.g. Customers)")
    parser.add_argument("--entity-namespace", help="Full namespace of the entity")
    parser.add_argument("--context-file", help="Path to *MongoDbContext.cs (auto-detected if omitted)")
    parser.add_argument("--register-repository", action="store_true",
                        help="Also register a custom MongoDbRepository in the module")
    parser.add_argument("--repository-namespace",
                        help="Namespace of the custom repository (e.g. MyProject.Data.Customers)")
    parser.add_argument("--repository-name",
                        help="Class name of the custom repository (e.g. MongoCustomerRepository)")
    parser.add_argument("--module-file", help="Path to the *Module.cs (auto-detected if omitted)")
    parser.add_argument("--cwd", help="Override working directory")
    args = parser.parse_args()

    ctx = load_or_prompt_config(args.cwd)

    entity = args.entity or _prompt("Entity name")
    if not entity:
        print("Entity is required.", file=sys.stderr)
        return 2
    plural = args.plural or _prompt("Plural / collection name", entity + "s")
    default_ns = f"{ctx.root_namespace}.Entities.{plural}" if ctx.root_namespace else ""
    entity_ns = args.entity_namespace or _prompt("Entity namespace", default_ns)
    if not entity_ns:
        print("Entity namespace is required.", file=sys.stderr)
        return 2

    if args.context_file:
        ctx_file = Path(args.context_file)
    else:
        detected = _find_context_file(ctx)
        ctx_file = Path(_prompt("Path to *MongoDbContext.cs", str(detected) if detected else ""))
    if not ctx_file.is_file():
        print(f"Context file not found: {ctx_file}", file=sys.stderr)
        return 2

    changes = _update_context(ctx_file, entity, plural, entity_ns)
    if changes:
        print(f"[OK] {ctx_file}")
        for c in changes:
            print(f"  + {c}")
    else:
        print(f"[skip] {entity} already registered in {ctx_file}")

    if args.register_repository:
        repo_name = args.repository_name or f"Mongo{entity}Repository"
        repo_ns = args.repository_namespace or (
            f"{ctx.root_namespace}.Data.{plural}" if ctx.root_namespace else ""
        )
        if not repo_ns:
            print("--repository-namespace required for --register-repository",
                  file=sys.stderr)
            return 2
        if args.module_file:
            module_file = Path(args.module_file)
        else:
            detected_mod = _find_module_file(ctx)
            module_file = Path(_prompt("Path to *Module.cs",
                                        str(detected_mod) if detected_mod else ""))
        if not module_file.is_file():
            print(f"Module file not found: {module_file}", file=sys.stderr)
            return 2

        mod_changes = _update_module(module_file, entity, repo_name, repo_ns, entity_ns)
        if mod_changes:
            print(f"[OK] {module_file}")
            for c in mod_changes:
                print(f"  + {c}")
        else:
            print(f"[skip] {entity} repository already registered in {module_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
